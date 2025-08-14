# RayInfo 2025

RayInfo 是一个信息聚合器，作者是 Maxiee（Maeiee），是他对抗算法投喂、夺回注意力主权的宣言。

RayInfo 由前后端两部分组成：

- 后端：使用 Python 编写，基于 FastAPI + APScheduler，通过 Playwright 实现自动化抓取。
- 前端：使用 Flutter 编写，支持 Android、iOS、Web 和桌面端。

## RayInfo 后端

技术栈：

- 语言： Python 3.11+
- Web框架： FastAPI
- 调度器： APScheduler (AsyncIOScheduler)
- 浏览器自动化： Playwright
- 数据库： SQLite
- 运行环境： Mac Mini M4 (通过uvicorn长期运行)，通过 tailscale 组成内网 + 公网暴露

## 采集架构设计（Draft v0.1）

本章节聚焦后端“采集器（Collector）”体系与调度集成方案，目标是在未来支持大量异构来源（微博 / X / RSS / 定制站点），并具备：

1. 易扩展：新增一个来源 ≤ 30 分钟脚手架 + 少量业务代码。
2. 高内聚低耦合：采集逻辑、调度策略、数据清洗、持久化分层。
3. 配置驱动：任务参数、频率、开关位于中心化配置（数据库 + YAML + 环境变量覆盖）。
4. 可水平扩展：Collector 无状态（或最小状态），允许多进程/多机并行；Playwright 浏览器池共享。
5. 可观测：每个任务具备统一 Job ID、Tracing、指标、告警钩子。
6. 任务爆炸可控：支持“参数化 Collector” -> 任务拆分 / 分片 / 节流 / 回压。
7. 失败自愈：指数退避 + jitter、幂等写入、断点续跑（分页游标、时间窗口）。

### 总体数据流（逻辑层次）

Source -> Collector 抓取 -> (可选) 解析/标准化 -> Pipeline (去重 -> 富化(补充元数据) -> 持久化) -> 出口(数据库 / 队列 / Webhook)

### 核心抽象

1. BaseCollector
	 - name: 唯一名称（如 weibo.home, weibo.user_feed）
	 - mode: one-shot / streaming / parameterized
	 - supports_parameters: bool
	 - fetch(context: CollectorContext, param: TaskParam | None) -> Iterable[RawEvent]
	 - state 序列化（分页游标、上次时间戳）可选：load_state() / save_state()
2. TaskDefinition
	 - collector_name, param_hash, schedule (cron/interval)、enabled、priority、retry_policy
3. TaskInstance（运行态）
	 - id（= f"{collector_name}:{param_hash}:{epoch_ts}"）
	 - tracing_id, attempts, next_backoff
4. PipelineStage
	 - process(records: list[Record]) -> list[Record]
	 - 类型：DeduplicateStage, EnrichStage, PersistStage 等
5. CollectorRegistry
	 - 注册 / 发现 Collector
	 - 提供 metadata: version, default_schedule, parameter_schema
6. SchedulerAdapter（封装 APScheduler）
	 - add_or_update_job(TaskDefinition)
	 - remove_job(id)
	 - event hooks: on_job_error, on_job_missed, on_job_executed
7. RateLimiter / ConcurrencyController
	 - 基于 token bucket + per-domain 限制
8. BrowserPool (Playwright)
	 - 复用浏览器上下文；Collector 通过上下文工厂获取 page

### 目录结构建议

```
rayinfo_backend/
	src/rayinfo_backend/
		app.py                # FastAPI 入口，包含启动事件 -> init scheduler
		config/
			settings.py         # Pydantic Settings (env + defaults)
			collector_configs/  # 静态配置模板 (YAML/JSON)
				weibo.yaml
		collectors/
			base.py             # BaseCollector 抽象 & 统一错误类型
			registry.py         # CollectorRegistry 实现
			common/
				context.py        # CollectorContext, BrowserHandle 等
				exceptions.py
			weibo/
				__init__.py
				home.py           # 首页时间线（单实例）
				user_feed/
					__init__.py
					collector.py    # 参数化采集器 (用户列表)
					strategies.py   # 分片/并发/增量策略
					parsers.py      # HTML/JSON -> 标准结构
			x/
				...               # 类似 weibo 结构
			rss/
				base_rss.py       # 通用 RSS 抽象
				sources/
					some_feed.py
			custom/
				example_site/
					collector.py
		scheduling/
			scheduler.py        # APScheduler 封装 (SchedulerAdapter)
			job_loader.py       # 从 DB/配置生成 TaskDefinition
			task_builder.py     # 参数集合 -> TaskDefinition 列表
			backoff.py          # 重试 & 指数退避策略
		models/
			task.py             # TaskDefinition, TaskInstance
			content.py          # 规范化后的 Content 数据结构
			raw_event.py        # 原始抓取数据
			source.py           # SourceMeta
		pipelines/
			base.py
			dedup.py
			enrich.py
			persist.py
		storage/
			repositories/
				content_repo.py
				task_repo.py
		services/
			rate_limit.py
			browser/
				browser_pool.py
		utils/
			time.py
			hashing.py
			logging.py
		instrumentation/
			metrics.py
			tracing.py
```

### APScheduler 集成策略

1. 启动流程：
	 - 加载配置 -> 初始化 CollectorRegistry -> 初始化 Pipeline -> 初始化 SchedulerAdapter。
	 - 调用 job_loader.sync()：从 task_repo / 配置生成 TaskDefinition 集合。
	 - 为每个 TaskDefinition 调用 adapter.add_or_update_job()。
2. 动态变化：
	 - 配置热更新（轮询或 Webhook） -> 重新 diff TaskDefinition -> 调整 APScheduler 任务。
	 - 参数化 Collector（如 weibo.user_feed）不直接为每个用户创建重量级任务：
		 a. 维护一个“参数聚合 Job”（例如 1 分钟执行）
		 b. 该 Job 内部根据策略对用户参数切片，批处理（batch）或生成内部并发协程
		 c. 子任务级别的重试由内部协程策略处理，不放大 APScheduler 任务数。
3. Job ID 规范：
	 - 静态 Collector: `{collector_name}` （如 weibo.home）
	 - 聚合/参数化调度 Job: `{collector_name}:aggregator`
4. 失败策略：
	 - APScheduler job 级失败：记录失败计数，超阈值 -> 降级（暂停 / 降频）
	 - 采集内部异常：按照粒度：网络/速率限制 -> backoff；解析错误 -> 计数并告警；身份失效 -> 触发 re-login 流程。

### 任务参数化与分片（微博 user_feed 示例）

需求：给定一个可配置用户列表（可能上千），按各自采集周期更新。

设计：
1. 用户配置来源：task_repo.user_sources (字段：user_id, screen_name, frequency, enabled)
2. 聚合 Job (weibo.user_feed:aggregator) 每 T=1min 运行：
	 - 读取需要在当前窗口内 due 的用户（`now >= last_run + frequency`）
	 - 根据优先级/滞后时间排序
	 - 分片策略：
		 a. 固定 batch 大小 (例如 20 用户 / 批)
		 b. 或动态：根据上一轮平均耗时 & RateLimit 预算计算 `batch_size = min(max_batch, available_tokens / avg_req_per_user)`
	 - 对每个 batch 并发 fetch（协程级别），内部应用 rate_limit。
3. 单用户子流程：
	 - 构造参数对象 UserFeedParam(user_id, since_cursor)
	 - 调用 BaseCollector.fetch(param)
	 - 解析 -> Pipeline -> 更新用户 last_run, 游标 since_cursor（例如最新一条微博 ID）

好处：APS 任务数 O(1)，内部并行 O(N)，总控点清晰。

### 状态管理

1. 轻量状态（分页游标、last_id、last_timestamp）写入 task_repo（例如 sqlite 表 collector_state）
2. 采用 upsert，保证幂等。
3. 大状态（复杂缓存）使用外部 KV（后续可引入 Redis）。

### Rate Limit & 并发控制

多层：
1. Domain 级：例如 weibo API 限 100 req/min -> token bucket（定时 refill）。
2. 用户批次级：限制单次批处理耗时不超过窗口（如 45s），防止拖慢下一轮。
3. Page 级：浏览器上下文并发上限（BrowserPool 设定 max_pages）。

### Pipeline 设计

串行阶段 + 背压：
1. DedupStage：用哈希指纹 (hash(normalized_text + author + ts))，BloomFilter 或 LRU Set。
2. EnrichStage：补充来源平台、语言检测、URL 展开。
3. PersistStage：批量写入数据库（事务 or 批插入）。

Pipeline 可配置（settings.PIPELINE_STAGES = ["dedup", "enrich", "persist"]）。

### 配置体系

优先级：环境变量 > 数据库覆盖 > YAML 默认。示例 weibo.yaml：
```
collectors:
	weibo:
		home:
			schedule: "*/2 * * * *"   # 每2分钟
		user_feed:
			aggregator_interval_seconds: 60
			default_user_frequency_seconds: 300
			max_batch_size: 30
```

### 可观测性

- metrics: scrape_duration_seconds, records_fetched_total, records_persisted_total, task_failures_total, rate_limit_wait_seconds
- tracing: span 层级 = job -> batch -> user_fetch -> pipeline
- 日志结构化：JSON (level, ts, collector, task_id, event)
- 告警阈值：连续错误次数 / 拉取延迟 > SLA。

### 新增 Collector 步骤示例（X 平台）

1. 在 collectors/x/ 新建模块，继承 BaseCollector。
2. 实现 parameter_schema（若需要参数）。
3. 在 registry.py 注册。
4. 添加默认配置 YAML。
5. （可选）编写解析与策略文件。
6. 更新 job_loader 识别新的 collector（多为自动通过 registry）。

### 错误分类与重试策略

| 类型 | 示例 | 策略 |
|------|------|------|
| TransientNetwork | 超时、连接重置 | 指数退避 (base=2s, max=60s, jitter) |
| RateLimited | HTTP429 / 明确速率提示 | 解析重试等待头信息 reset 时间 |
| AuthExpired | Cookie 失效 | 触发刷新，若失败 -> 暂停相关 Collector |
| ParseError | DOM/JSON 结构变化 | 记录 + 告警，样本入 inspection 队列 |
| Permanent | 资源不存在 | 标记任务失败，不重试 |

### 演进路线

阶段 0：当前基础 + 引入目录骨架 + BaseCollector + Registry。

阶段 1：微博 home / user_feed 落地，参数化聚合 Job，Pipeline 3 阶段 + 结构化日志。

阶段 2：引入 metrics + tracing + rate limit + retry/backoff 统一。

阶段 3：RSS 通用化、X 平台接入；支持多进程或分布式（换用持久化 APScheduler / 改成 Celery/Arq）。

阶段 4：任务优先级队列、Web UI 管理（启停 / 频率调节 / 观测仪表板）。

### 简要类草图（伪代码）

```python
class BaseCollector(ABC):
		name: str
		supports_parameters: bool = False
		default_schedule: str | None = None  # cron 或 None

		async def setup(self, ctx: CollectorContext): ...  # 可选初始化
		@abstractmethod
		async def fetch(self, ctx: CollectorContext, param: Any | None) -> AsyncIterator[RawEvent]: ...
		async def save_state(self, ctx, state): ...
		async def load_state(self, ctx) -> Any: ...

class WeiboUserFeedCollector(BaseCollector):
		name = "weibo.user_feed"
		supports_parameters = True
		async def fetch(self, ctx, param: UserFeedParam):
				# 获取页面 / API -> yield RawEvent
				...
```

### 结论

通过“参数化聚合 Job + Collector 抽象 + Pipeline + 配置驱动”的结构，既避免 APScheduler 任务数爆炸，又保证新增来源的低摩擦和运行时可观测性，为后续分布式扩展和 UI 管理奠定基础。

> 后续在 v0.2 将补充：完整 Pydantic 模型、任务状态表结构、metrics 清单、示例实现代码。




