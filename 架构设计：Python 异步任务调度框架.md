我在设计一个基于 Python AsyncIO 的异步任务调度框架 RayScheduler，本文档是对该框架的完整技术方案。
## 概念
### 任务生产者（TaskConsumer）

任务源（TaskConsumer）是任务的源头，负责生成任务，以及消费任务。

采用 OOP 继承设计方式：
- `BaseTaskConsumer`：任务源的基类，开发者需要基于该类派生出各种任务源。每种任务源表示一种特定的任务。

`BaseTaskConsumer` 核心属性：
- `name`：唯一标识
- `concurrent_count`：限制任务并发数，默认为1

核心抽象方法，需由子类实现：
- `produce(args: dict) -> Task`：根据输入参数创建一个 Task 任务，允许传入 `args` 参数
- `consume(task: Task)`：消费一个任务，执行对应具体操作

### 任务（Task）

任务（Task）是调度器调度的最小单元。由 TaskConsumer 创建以及消费。所有的 TaskConsumer 都共用同一个 Task 类型。

`Task` 核心属性：
- `uuid: str`：每个 Task 在创建时，具备唯一 uuid
- `args: dict`：传入 Task 的参数，用于在 TaskConsumer 消费时使用
- `source: str`：Task 在创建时，会持有对应的 TaskConsumer 的 `name`
- `schedule_at: datetime`：Task 在创建时，会有一个调度时间戳，指向未来，以 `datetime.now` 作为默认值

核心方法：
- `to_dict`：将 `uuid`、`args`、`source`、`schedule_at` 转为一个字典，用于持久化或者日志打印
- `from_dict`：将 `to_dict` 生成的字典恢复成 Task 实例。

### 任务生产者注册表（TaskConsumerRegistry）

这是一个全局单例，供开发者注册 TaskConsumer。

核心数据结构：
- `sources: dict[str, TaskConsumer]`：Key 为 TaskConsumer 的 name，value 为 TaskConsumer 的实例。

核心方法：
- `register(soruce: TaskConsumer)`：注册 TaskConsumer。
- `find(name: str) -> Optional[TaskSource]`：根据名称寻找对应的 TaskConsumer 实例。

## 调度器（Scheduler） 

Scheduler 负责基于 AsyncIO 对 Task 进行**时间驱动**与**并发受控**的异步调度。其核心目标：
- 按 Task.schedule_at 顺序触发任务（最早优先）
- 按 Task.source 的并发上限进行限流
- 空闲时不忙等，新任务/更早任务到来时可被立即唤醒
- 失败任务最小实现仅记录日志，不做重试（为下一阶段扩展预留接口）

### **职责边界**
- **只负责调度**：不负责任务产生（由 TaskSource.produce）与业务执行细节（由 TaskSource.consume）。
- **并发约束在源级别**：对每个 TaskSource.name 维持独立的并发信号量。
- **时间语义**：以 UTC 时间作为统一时基进行到点判断。
- **最小可靠性**：内存级队列，无持久化；未知 Source 的 Task 直接丢弃并记录错误。

### **核心数据结构**
#### **内部堆队列（最小触发时间优先）**
- 结构：`heap: list[(when_ts: float, seq: int, task: Task)]`
    - when_ts：task.schedule_at 转为 UTC 后的 POSIX 秒
    - seq：自增序列，确保在同一触发时间下的**稳定出队顺序**（避免 Python 元组比较 task 对象）
    - task：任务本体
- 不变式（Invariants）：
    1. heap 始终保持**小顶堆**性质（堆顶为最早触发任务）
    2. seq 严格递增，单调不减
    3. 任意时刻 len(heap) = 待触发任务数

#### **唤醒事件**
- `event: asyncio.Event`
    - 语义：**有更早/新任务加入**或**需要尽快重算下一次唤醒时间**时置位
    - 约束：进入等待前必须 event.clear()，避免消费历史信号

#### **源级并发控制**
- `_sem_by_source: dict[str, asyncio.Semaphore]`
    - 懒创建：首次执行到某源任务时，根据 `TaskConsumerRegistry.find(source).concurrent_count` 初始化
    - 语义：调度某源任务前 `await sem.acquire()`，完成后 `sem.release()`

#### **运行状态**
- `_running: bool`：调度器生命周期开关
- `_task_dispatcher`: asyncio.Task | None：主循环任务句柄
- `_seq: int`：堆内条目去歧义序列号
- `_log: logging.Logger`：结构化日志记录器

### **外部接口（API）**

#### **add_task(task: Task) -> None**
- 功能：向调度器提交一个待执行任务
- 行为：
    1. 计算 `when_ts = to_utc(task.schedule_at).timestamp()`
    2. `heapq.heappush(heap, (when_ts, seq, task)); seq += 1`
    3. event.set() 唤醒调度器主循环（可能出现“更早任务插队”）
- 复杂度：O(log N)（N 为待触发任务数）
- 线程/协程语义：**预期在同一事件循环中调用**；暂不考虑跨线程调用场景。
#### **await start() -> None**
- 功能：启动调度器主循环（幂等）
- 行为：`设置 _running=True`，创建 `_task_dispatcher = create_task(_dispatcher_loop())`
#### **await stop() -> None**
- 功能：有序停止调度器
- 行为：
    1. `_running=False`
    2. `event.set()` 以打断阻塞等待
    3. `await _task_dispatcher` 等待主循环自然退出
- 注意：**不取消**已在执行中的业务协程（它们将自行完成）；如需强制终止，属后续增强项

### **内部方法与算法**

#### **_dispatcher_loop()**
- 职责：**时间驱动 + 唤醒可中断等待 + 触发任务**    
- 主流程（伪代码）：

```
log "Scheduler started"
while _running:
    if heap 为空:
        event.clear()
        await event.wait()              # 直到新任务到来
        continue

    (when, _, task) = heap[0]           # 只窥视堆顶，不弹出
    now = utc_now_ts()
    delay = max(0, when - now)
    if delay > 0:
        event.clear()
        await FIRST_COMPLETED(          # 二选一就绪
            event.wait(),               # 更早任务插入或显式唤醒
            sleep(delay)                # 时间到点
        )
        continue                        # 重新计算堆顶与 delay

    heapq.heappop(heap)                 # 到点：弹出
    create_task(_run_task_once(task))   # 不阻塞主循环，放入执行态
log "Scheduler stopped"
``` 
- 关键语义：
    - **两路等待**：event.wait() 与 sleep(delay) 并行竞争，谁先完成以谁为准；从而兼顾“到点触发”与“更早任务插队”
    - **无忙等**：空堆/未到点均为挂起状态，对 CPU 友好
    - **非阻塞触发**：业务执行放入独立协程，主循环仅负责“点火”
#### **_run_task_once(task: Task)**
- 职责：执行单个任务的业务消费，并遵循源级并发上限
- 流程：
    1. `src = TaskConsumerRegistry.find(task.source)`；若为空：`log.error("[drop] Unknown task source...")` 并返回
    2. `sem = _get_sem(task.source)`（懒创建，容量=`src.concurrent_count`，缺省 1）
    3. `await sem.acquire()`
    4. `try: await src.consume(task) except Exception: log.exception("[fail] ...") finally: sem.release()`
- 说明：
    - **失败处理**：最小实现仅记日志，不重试、不回队；
    - **公平性**：同源内由信号量串/并控制；跨源由各自信号量独立调度
### **时间与时钟语义**

- `Task.schedule_at` 要求为**时区感知型** datetime，调度器内部统一转为 **UTC** 计算触发点
- Past-due 语义：若 `schedule_at <= now(UTC)`，任务将在下一个调度循环**立即触发**
- **系统时钟变更风险**：当前实现使用墙钟（`datetime.now(timezone.utc)`）——若系统时间被回拨/快进，可能引发早/晚触发的抖动
    - 备选（后续）：以事件循环的**单调时钟**（loop.time()）为基准，用“绝对时刻→相对延迟”的映射层消除系统时钟跳变影响
### **并发与资源管理**

- **源级并发**：每个 TaskSource.name 绑定一个 `asyncio.Semaphore(concurrent_count)`
    - 取值策略：从 Registry 读取，若缺省或异常取 1
    - 释放保障：try/finally 确保异常/取消情况下释放令牌
- **全局并发**：**未设置**（最小实现）。若需要全局上限，可在 `_run_task_once` 外围再加一层全局 Semaphore
- **任务风暴**：当同一时刻大量任务到点，调度器会创建同样数量的执行协程；源级并发会阻挡执行但不会限制**创建数量** —— 可能导致**瞬时内存高峰**（后续可加全局并发或就绪队列阈值）

### **错误处理与降级策略**

- **未知源**：`Registry.find(name)` 失败 → **丢弃任务**并 `log.error([drop] Unknown task source, task_dump)`
- **消费异常**：consume 抛出异常 → `log.exception([fail] ...)`，不重试、不回队
- **主循环健壮性**：主循环异常由顶层 try/finally 兜底记录“stopped”，但**不自动重启**（后续可选）

> 注：重试/回退/死信队列/持久化等均为下一阶段的增强点，故此处显式列为**非目标**以避免歧义。

### **生命周期与停止语义**

- **Start**：幂等，多次调用仅首次生效
- **Stop**：
    - 停止仅影响**新的触发**；已创建的业务协程**继续执行直至完成**
    - 不对正在运行的 consume 执行取消（保持业务幂等与资源释放简单化）
    - 若需要“优雅关机超时后强制取消”，建议后续引入“停止超时 + task.cancel()”策略

### **复杂度与性能评估**

- **入队**：add_task 为 O(log N)
- **出队**：到点触发 O(log N)
- **空闲成本**：零（挂起等待）
- **调度精度**：受事件循环与操作系统调度影响，通常在毫秒—几十毫秒级抖动；对硬实时不适用

### **线程安全性与集成约束**

- 调度器预期在**单事件循环**内使用；跨线程提交任务场景目前暂不考虑
- 与 Web 框架（如 FastAPI）集成时，建议：
    - 在应用启动钩子中 `await scheduler.start()`
    - 在应用停止钩子中 `await scheduler.stop()`
- 分布式/多进程：当前实现**不支持**；注册表为进程内单例，信号量为进程内对象

### **日志与可观测性（最小版）**

- **启动/停止**：`INFO: "Scheduler started/stopped"`
- **丢弃**：未知源 → `ERROR: "[drop] Unknown task source: {source} {task_dump}"`
- **失败**：consume 异常 → `ERROR + 堆栈 "[fail] task {uuid} from {source}: {exc}"`
- **建议的后续指标**（本版未实现）：
    - scheduler.queue.size（len(heap)）
    - scheduler.task.started/finished/failures（总量/分源）
    - scheduler.dispatch.latency_ms（到点到实际触发的延迟）
    - semaphore.available{source}（分源可用令牌）

### **边界条件与行为约定**

1. **同一触发时间的多任务**：按插入序列 seq 稳定排序（FIFO 语义）  
2. **过去时间的任务**：视为**立即可触发**
3. **大批量任务同时到点**：立即创建等量协程，执行受源级信号量限制；若担心内存，可引入全局限流或按批提取
4. **时钟跳变**：本版依赖墙钟；生产环境建议切换到单调时钟基线
5. **任务去重/幂等**：交由业务侧（Task.uuid 仅用于标识与日志，不做去重）

### **与系统其它组件的交互**

- **与 Task**：Scheduler 仅读取 uuid / source / schedule_at / args；不修改任务内容
- **与 TaskSource**：依赖 Registry.find(name) 查找实例，并调用 await source.consume(task)
- **与 Registry**：只读；未提供运行时注册/注销的订阅机制（最小实现）

### **扩展点（后续阶段）**

> 以下为清晰的演进插槽，不在本版最小实现范围内。

1. **重试策略**：最大次数 / 退避（指数/固定）/ 可观察死信队列    
2. **可插拔持久化**：内存 / Redis / SQLite / Postgres（支持恢复与“至少一次”语义）
3. **全局并发上限**：在源级信号量之外加总量阈值
4. **时间基线切换**：UTC 墙钟 → 事件循环单调时钟
5. **分布式调度**：对接共享任务队列（如 Redis Stream / SQS），以及分布式租约/选主
6. **取消与优雅关机**：停止时对执行中任务设置**超时取消**策略
7. **可观测性完善**：指标上报、追踪（trace id 与 Task.uuid 关联）、结构化日志

### **设计取舍（Why）**

- **堆 + 事件二路等待**：在不引入复杂定时器管理的前提下，实现“到点触发 + 更早任务插队”的**可中断睡眠**，避免忙等
- **源级信号量**：最小成本实现“同类任务并发上限”；比队列分片或工作池更轻量、直观
- **不持久化**：首版以纯内存交换换取实现简洁；将可靠性留到可插拔阶段
- **不重试**：明确最小语义，避免早期把失败语义复杂化（后续再引入退避策略）

### **最小行为验收清单（建议用例）**

1. **顺序触发**：投递 t0 < t1 < t2 三个任务，观察按时序触发
2. **插队唤醒**：已有一个 t+5s 任务等待时，在 +0.5s 时刻投递一个 t+1s 任务，应在 ~+1s 触发，不受原 +5s 影响
3. **过去任务**：schedule_at=now-1s 应立刻触发
4. **并发上限**：同源 concurrent_count=1 连投 3 个任务，确保严格串行；同源 =2 时应最多并行两个
5. **未知源**：投递未知 source 的任务，被丢弃并记录错误日志
6. **停止语义**：大量任务执行中调用 stop()，应立即停止新的触发，但已在运行的任务自然完成
