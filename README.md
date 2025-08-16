# RayInfo 2025

RayInfo 是一个信息聚合器，作者是 Maxiee（Maeiee），是他对抗算法投喂、夺回注意力主权的宣言。

RayInfo 由前后端两部分组成：

- 后端：使用 Python 编写，基于 FastAPI + APScheduler，通过 Playwright 实现自动化抓取。
- 前端：使用 Flutter 编写，支持 Android、iOS、Web 和桌面端。

## RayInfo 后端

后端“采集器（Collector）”体系与调度集成方案，目标是在未来支持大量异构来源（微博 / X / RSS / 定制站点），并具备：

1. 易扩展：新增一个来源 ≤ 30 分钟脚手架 + 少量业务代码。
2. 高内聚低耦合：采集逻辑、调度策略、数据清洗、持久化分层。
3. 配置驱动：任务参数、频率、开关位于中心化配置（数据库 + YAML + 环境变量覆盖）。
4. 可水平扩展：Collector 无状态（或最小状态），允许多进程/多机并行；Playwright 浏览器池共享。
5. 可观测：每个任务具备统一 Job ID、Tracing、指标、告警钩子。
6. 任务爆炸可控：支持“参数化 Collector” -> 任务拆分 / 分片 / 节流 / 回压。
7. 失败自愈：指数退避 + jitter、幂等写入、断点续跑（分页游标、时间窗口）。

技术栈：

- 语言： Python 3.11+
- Web框架： FastAPI
- 调度器： APScheduler (AsyncIOScheduler)
- 浏览器自动化： Playwright
- 数据库： SQLite
- 运行环境： Mac Mini M4 (通过uvicorn长期运行)，通过 tailscale 组成内网 + 公网暴露

总体数据流：

Source -> Collector 抓取 -> (可选) 解析/标准化 -> Pipeline (去重 -> 富化(补充元数据) -> 持久化) -> 出口(数据库 / 队列 / Webhook)

### 应用入口

路径：`rayinfo_backend/app.py`。首先初始化一个 FastAPI 实例，然后 APScheduler 以 lifespan 的方式与 FastAPI 生命周期集成，这样实现了 HTTP Server 与调度器的无缝协作。

### 核心抽象

- BaseCollector：负责去不同网站把原始信息抓起来，像一个自动抓取信息的机器。
- TaskDefinition：描述要做哪项抓取工作、带什么参数和什么时候执行，就像一张任务单。
- TaskInstance（运行态）：任务被实际运行时的那次记录，有唯一 ID 和重试信息，像一次任务的执行事件单。
- PipelineStage：传送带上的一个工位，负责把事件去重、补充信息或写入数据库，像工厂里的单个工序。
- CollectorRegistry：保存并管理所有采集器的信息，像一个采集器的电话簿或目录。
- SchedulerAdapter（封装 APScheduler）：把任务交给闹钟系统并在到点时唤醒它们，像值班的提醒员。
- BrowserPool (Playwright)：共享和复用浏览器实例，避免每次都打开新浏览器，像公共的浏览器工具箱。

### APScheduler 调度器

闹钟（APScheduler） -> 叫醒（job_wrapper） -> 捞（collector.fetch） -> 收集（events 列表） -> 传送带加工（Pipeline） -> 完成。

记住这 7 个词：闹钟、叫醒、捞、收、带、存、等下一轮。

#### 集成策略

在 app.py 的 FastAPI lifespan 中，首先创建 `SchedulerAdapter` 实例，然后调用 `adapter.start()` 启动 APScheduler。这样可以确保调度器在 FastAPI 启动时就开始运行。

在创建 `SchedulerAdapter` 时，调用 `load_all_collectors()` 来加载所有已注册的 Collector。

`finally` 表示 FastAPI 关闭时，调用 `adapter.shutdown()` 来优雅地停止 APScheduler。

#### SchedulerAdapter

APScheduler 是工厂里强大的“自动闹钟系统”。可以把 `SchedulerAdapter` 想成“值班班长 + 传送带按钮控制员”。

`SchedulerAdapter` 负责：

1. 把“要做的活”（各个 Collector）登记成定时闹钟（Job）。
2. 到点时叫醒对应的 Collector 去“捞数据”。
3. 把捞回来的原始数据丢到后面的 Pipeline 传送带上继续加工（去重 / 持久化）。

源码位置：`scheduling/scheduler.py`

##### 一次执行完整旅程（时间线）

1. 启动：`adapter.start()` -> APScheduler 启动自己的事件循环任务管理。
2. 注册：`add_collector_job` 为每个 Collector 设一个“每 N 秒”的 IntervalTrigger。
3. 到点：APScheduler 内部 tick 到达 -> 找出 due 的 job -> `await job_wrapper()`。
4. 包装层：`job_wrapper` 调 `run_collector_once`。
5. 抓取：`collector.fetch()` 返回一个异步生成器（像一条“逐条往外吐”的鱼篓）。
6. 收集：`async for` 把生成器里产生的每个事件装进 `events` 列表。
7. 加工：不为空则 `pipeline.run(events)`（依次执行 Dedup -> Persist）。
8. 结束：本轮完成，等待下一个间隔。

##### collector.fetch() 

产出的一组 RawEvent 是什么？

- fetch 是一个“异步生成器”→ 它会一条一条 yield RawEvent。
- 每 yield 一次，就表示“发现了一条新的原始内容”。
- 最终我们用 async for 把这些 yield 到的东西收集成一个 Python 列表 events（可能 0 条、1 条、N 条）。

一条微博 = 一个 RawEvent 吗？

- 是。我们把“最小有意义的内容单元”定义为一个 RawEvent。
- 抓微博首页：一个页面通常包含多条微博 → fetch 会循环那一页解析出来的每条微博并逐条 yield → 这页可能就 yield 出 20 个 RawEvent。
- 如果是只抓一个“单条详情页”，确实可能只 yield 1 个 RawEvent（列表长度=1）；但依旧保持“统一处理：列表传入 pipeline”。

##### 为什么要“先收集成列表再交给 pipeline”？

- 方便做“批处理”优化（去重、批量入库、一次事务）。
- Pipeline 现在是同步串行接口 process(list)，最简单、易调试。
- 后面如果需要“边产出边处理”，可以改成流式（async）或分块 flush。

##### pipeline 如何处理 RawEvent 列表

伪代码：

```python
events = list(async_fetch_generator)  # e.g. 20 条
for stage in pipeline.stages:
    events = stage.process(events)    # 每个阶段接收并返回（可能过滤）
# 结束后 events 是最终要持久化/输出的结果
```

Pipeline 如何“一个一个加工”？ 

RayEvent 列表统一传入一个 Stage，Stage 完成后返回新的列表，再传入下一个 Stage。

DedupStage.process:

- 建一个 seen 指纹集合（对象属性里缓存）。
- 遍历传入的 events 列表：
    - 对每个 e 计算 fingerprint（例如 f = hash(e.source + e.raw.get('id',''))）
    - 若 f 在 seen：丢弃（不放入输出列表）
    - 否则加入 seen，并收集到新的 output 列表
- 返回去重后的列表（可能比原来短）

##### FAQ

1. 问：为什么使用 IntervalTrigger 而不是 Cron？
   答：早期 Collector 多为“固定频率拉取”，Interval 更直接；后续如需“每天 8:00”再扩展 CronTrigger。
3. 问：如果抓取时中途抛错会怎样？
   答：当前会直接冒出到 APScheduler，日志记录；后续会添加 try/except 包装并统计失败次数。
4. 问：Pipeline 没有 Enrich 阶段吗？
   答：暂未实现，等出现实际富化需求再加，结构已留好插槽。
5. 问：为什么 Pipeline 是同步的？
   答：先保持简单；真正 I/O 富化出现时再异步化，避免过早复杂度。

### RawEvent

`RawEvent` 是系统里一条“刚捞上来、还没加工”的原始信息数据。可以把它理解为：

> 捕到的一条“信息小鱼”——还带着海水（原始字段），还没挑刺（去重）、没切片（富化）、没装盒（持久化）。

一句话说明：RawEvent 就是刚抓到的原始记录，像一条未加工的信息素材。

“源（source）+ 内容包（raw）+ 时间戳（fetched_at） = 原始事件快照”。

看到 RawEvent，就想到：这只是“素材”，真正的“产品”要等 Pipeline 加工后才出现。

源码：`collectors/base.py`

RawEvent 的作用：

1. 解耦：Collector 只负责“抓”，不负责“怎么存 / 怎么去重”。
2. 可扩展：不同平台字段千奇百怪，统一包一层，后续 Pipeline 可以逐步规范化。
3. 便于幂等：`(source, raw["id"])` / 内容指纹 可作为去重键。
4. 观测：统一结构可以统计“每次抓到多少条”“延迟多大”。

生命周期（从出生到落库）：

1. 由 Collector 的 `fetch()` `yield RawEvent(...)` 诞生。
2. SchedulerAdapter 聚合成列表 `events`。
3. Pipeline 依次处理：DedupStage -> (未来：EnrichStage) -> PersistStage。
4. 被写入数据库 / 发送到下游后，它的“原始形态”可能被保留（全文）或只存关键字段。

#### RawEvent 对应内容粒度

看页面承载的粒度：

- 页面里含多条内容（如 timeline、列表页）：多条 RawEvent。
- 页面本身就是唯一对象（如某个用户档案、一个统计数）：1 条 RawEvent。

即：页面 ≠ RawEvent；页面只是“容器”，RawEvent 是“最小内容颗粒”。

##### 未来可能演进

1. 增加 `uid`（内部统一 ID），方便跨阶段引用。
2. 增加 `normalized` 字段或派生类，存标准化结果。
3. 增加校验层（Pydantic Model）在“进入 Pipeline 前”做格式检查。 
4. 引入压缩策略：raw 大字段（HTML / 长文本）按需裁剪或单独存储。

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

可组合的处理链（Pipeline），可理解为一个传送带。输入是一组 `RawEvent`，依次经过多个 Stage 函数式处理，输出仍是一组 `RawEvent`（内容可能被过滤或增强）。

通俗解释：想象有一条“信息传送带”。Collector 把刚捞上来的“原始信息石块”一把倒在传送带起点。沿路有一排小工位（Stage）：

1. 有的负责挑掉重复的石块（去重）。
2. 有的给石块贴标签、补备注（富化）。
3. 最后一个把合格的石块整齐放进仓库（持久化）。

传送带按顺序走，每个工位只专心做一件简单事。这样：

- 新加或调整步骤，只要“增 / 删 / 换”一个工位，不影响其它。
- 上游 Collector 不需要关心存库细节；下游也不用懂抓取逻辑。
- 以后要更快，只需让某些工位并行或换成更高级工具。

串行阶段 + 背压：

1. DedupStage：用哈希指纹 (hash(normalized_text + author + ts))，BloomFilter 或 LRU Set。
2. EnrichStage：补充来源平台、语言检测、URL 展开。
3. PersistStage：批量写入数据库（事务 or 批插入）。

Pipeline 可配置（settings.PIPELINE_STAGES = ["dedup", "enrich", "persist"]）。

代码位置：`rayinfo_backend/src/rayinfo_backend/pipelines/base.py`

抽象示意：

```
RawEvent List -> [Stage1] -> [Stage2] -> ... -> [StageN] -> Final List
```

核心类：

- `PipelineStage`: 抽象基类，定义 `process(events: list[RawEvent]) -> list[RawEvent]`。约定：
	- 输入/输出均为列表；
	- Stage 内部可以过滤、修改、扩展事件；
	- 建议保持幂等（同一输入多次执行结果一致），利于重放 / 重试；
	- 不直接抛出未分类异常，应该转换为可观测错误或记录并跳过；
- `DedupStage`: 维持一个内存内 `_seen` 容器（滑动窗口），根据 `post_id`（或原始内容字符串散列）去重；
- `PersistStage`: 目前只是打印（占位），后续会替换为批量持久化逻辑（事务、重试、幂等键约束）。
- `Pipeline`: 保存阶段列表并顺序执行。

设计意图：

1. 将“采集（抓原始事件）”与“清洗/富化/落库”解耦，Collector 只关心获取 RawEvent。
2. 通过 Stage 链式组合，可按需要增删阶段，不侵入上游 Collector。
3. 允许后续替换为异步/并行版本（Stage 接口未来可扩展为 `async process` 或者对大批量分块）。

扩展指南：

新增一个阶段（示例：简单情感打分）:

```python
from rayinfo_backend.pipelines.base import PipelineStage

class SentimentStage(PipelineStage):
		def process(self, events):
				for e in events:
						text = e.raw.get("text", "")
						e.raw["sentiment"] = simple_sentiment(text)  # 伪函数
				return events
```

然后在组装 Pipeline 时加入：

```python
pipeline = Pipeline([
		DedupStage(),
		SentimentStage(),
		PersistStage(),
])
```

规范 & 建议：

- 顺序敏感：去重应尽量放前（减少后续处理量），富化阶段次之，最终持久化放最后。
- 性能：若后续事件列表可能较大，Stage 内应避免 O(N^2) 操作；去重容器将演进为 BloomFilter / LRU Set 以降低内存。
- 幂等性：Persist 前的所有字段补充建议幂等，避免重复写入造成副作用；Persist 内部需基于唯一键（例如 `source + post_id`）做 Upsert。
- 失败处理：
	- 单条解析失败 -> 记录日志并跳过，不应中断整批；
	- 批处理失败（数据库暂时不可用）-> 整批重试（指数退避），必要时拆分批次；
	- Stage 级不可恢复错误 -> 上报 metrics + 告警，并可短路后续阶段。
- 观测（计划中）：为每个 Stage 记录 `input_count`, `output_count`, `duration_seconds`，形成链路指标。

未来演进方向：

1. Async 化：`process` 改为 `async`，允许 I/O（例如外部特征查询 / 向量服务）。
2. 并行批处理：对独立记录映射型 Stage（Map 类）使用并发（线程池 / asyncio.gather）。
3. 可配置装配：读取 `settings.PIPELINE_STAGES`（字符串列表）到工厂映射，实现声明式配置；支持按 Collector 类型定制。
4. 状态化 Stage：引入可持久化状态（如去重的持久 BloomFilter），并提供 `load_state/save_state` 钩子统一管理。
5. 错误路由：增加一个 Side Channel，把异常样本输出到“检视队列”供人工分析。

快速对比（当前 vs 目标）：

| 维度 | 当前 | 目标 |
|------|------|------|
| Stage 接口 | 同步, 简单列表 | 异步 + 流/批双模式 |
| 去重 | 内存列表滑窗 | 可选 BloomFilter / Redis Set |
| 配置 | 代码硬编码 | 配置 + 动态热更新 |
| 观测 | 控制台打印 | metrics + tracing + 结构化日志 |
| 错误处理 | 简单打印 | 分类、重试、旁路隔离 |

这样，Pipeline 在体系中的角色就非常明确：它是 Collector 输出到存储/下游之前的“加工传送带”，负责质量（去重）、增强（富化）、可靠（重试与幂等）与观测闭环。

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

### BrowserPool (Playwright)：

共享和复用浏览器实例，避免每次都打开新浏览器，像公共的浏览器工具箱。

RayInfo 启动后，自动启动 Playwright 浏览器示例，我希望实示例不以无头方式运行，以便于我观察调试。启动后，各个 Collector 可以通过 `BrowserPool` 获取浏览器上下文（Context）和页面（Page），从而执行抓取任务。

#### 浏览器池初始化

创建浏览器实例，并提供可供 Collector 访问的接口能力。接口能力需要具备扩展性，最初的能力包括创建页面、加载 URL，执行脚本等，未来如果想要扩充能力，能够很容易地扩展，同时代码又不至于很乱，始终保持可读性。

### 演进路线

阶段 0：当前基础 + 引入目录骨架 + BaseCollector + Registry。

阶段 1：微博 home / user_feed 落地，参数化聚合 Job，Pipeline 3 阶段 + 结构化日志。

阶段 2：引入 metrics + tracing + rate limit + retry/backoff 统一。

阶段 3：RSS 通用化、X 平台接入；支持多进程或分布式（换用持久化 APScheduler / 改成 Celery/Arq）。

阶段 4：任务优先级队列、Web UI 管理（启停 / 频率调节 / 观测仪表板）。

### 目录结构

```
__init__.py           # 标记这个目录是一个 Python 包
app.py                # 程序入口：启动 FastAPI 服务和调度器
config/               # 放配置相关代码
	settings.py         # 读取与管理配置（环境变量 + 默认值）
collectors/           # 各类“采集器”代码目录
	base.py             # 定义采集器的通用基类与基础错误
	weibo/              # 微博相关采集器代码
		__init__.py       # 标记微博采集器包
		home.py           # 抓取微博首页时间线数据
models/               # 放数据模型（结构定义）
	task.py             # 定义任务相关的数据结构
pipelines/            # 数据处理流水线（去重/加工等）的代码
	__init__.py        # 标记流水线包
	base.py            # 定义流水线的基础类与执行逻辑
scheduling/          # 调度相关代码
	scheduler.py        # 封装 APScheduler 的调度器
utils/               # 通用小工具
	logging.py         # 统一设置和使用日志输出
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




