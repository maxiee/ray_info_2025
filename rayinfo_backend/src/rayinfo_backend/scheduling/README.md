# scheduling 子包

本子包负责“采集器任务”的调度、状态管理与策略组织。其目标是：
- 人类可读：模块边界清晰、命名统一、职责单一。
- 可扩展：新增采集器或调度行为时只需扩展，不需修改核心代码。
- 可观测：关键路径具备日志与最小统计信息。

## 模块简介

- `scheduler.py`：对 APScheduler 的薄封装，提供面向业务的 `SchedulerAdapter`。
  - 负责：将 Collector 注册为调度任务、执行一次任务、状态更新和配额重试。
- `state_manager.py`：采集器执行状态的持久化（断点续传）。
  - 负责：最后一次执行时间、执行次数、是否应立即执行、下次执行时间计算等。
- `strategies.py`：原有策略模式实现（保留以兼容/参考）。当前核心路径使用 `SchedulerAdapter` 的状态感知调度。
- `types.py`：调度领域通用类型与工具（例如 JobKind、统一的 `make_job_id`）。

## 关键概念

- Collector（采集器）：实现 `fetch()`（或参数化的 `fetch(param=...)`）的实体。
- Job（任务）：按间隔触发的执行单元。我们用 `make_job_id()` 统一 ID 命名：
  - 普通：`<collector>:initial` / `<collector>:periodic`
  - 参数化：`<collector>:<param>:initial` / `...:periodic`
  - 配额重试：在上述基础上使用 `quota_retry` 并可加时间戳后缀。

## 扩展点

- 新增 Collector：
  - 普通：实现 `BaseCollector`，设置 `default_interval_seconds`。
  - 参数化：实现 `ParameterizedCollector`，实现 `list_param_jobs()` 返回 (param, interval) 序列。
- 新增调度行为：
  - 在 `SchedulerAdapter` 内部扩展，或在 `strategies.py` 新增策略并挂入注册表。

## 弃用与迁移

`strategies.py` 模块（`StrategyRegistry`、`JobFactory`、`*Strategy` 等）已标注为弃用，推荐直接使用 `SchedulerAdapter` 的状态感知接口：

- 单个采集器：`SchedulerAdapter.add_collector_job_with_state(collector)`
- 批量加载：`SchedulerAdapter.load_all_collectors()`

迁移步骤建议：
1. 移除对 `StrategyRegistry` 与 `JobFactory` 的直接依赖；
2. 在原本注册任务的地方，替换为通过 `SchedulerAdapter` 添加；
3. 对于参数化采集器，维持 `list_param_jobs()` 返回 `(param, interval)` 的约定即可，其余由调度器适配处理；
4. 若必须临时保留策略模式，注意该模块导入时会产生 `DeprecationWarning`，请尽快迁移。

## 约定

- 所有对数据库状态的更新通过 `CollectorStateManager` 完成。
- 任务 ID 必须使用 `types.make_job_id()` 生成，避免散落的字符串格式。
- 日志命名空间统一以 `rayinfo.scheduler` 开头（与历史保持一致）。

## 最小示例

在应用启动时：

```python
adapter = SchedulerAdapter()
adapter.load_all_collectors()
adapter.start()
```

手动触发一个实例：

```python
await adapter.run_instance_by_id(instance_id)
```

如遇配额限制，适配器会自动创建一次性重试任务，并跳过状态更新时间，以确保配额恢复后能尽快重跑。