from __future__ import annotations

from pydantic import BaseModel, Field


class TaskDefinition(BaseModel):
    """任务的静态定义（TaskDefinition）。

    说明：
    - 本类用于描述调度系统中一条“任务”的静态元数据（配置级别的信息），而不是任务在运行时的状态。
    - 这些字段应该可以被序列化到数据库或配置文件中（例如 YAML/JSON），并且便于通过接口传递与比对。

    设计要点（更易理解的逐项说明）：
    - id: 唯一标识字符串，用于在日志、监控和数据库中区分不同任务；建议包含采集器名与参数摘要，便于人工识别。
      例如："weibo.user_feed:12345" 或 "weibo.home"。
    - collector_name: 指向实现该任务逻辑的 Collector 名称，调度器会据此从 Registry 加载具体实现。
    - interval_seconds: 以秒为单位的周期间隔；调度器据此决定任务的重复频率。若为 0 或负值，表示不做周期性调度（可作为一次性任务）。
    - enabled: 开关位，控制调度器是否应激活该任务；用于临时停用任务或 A/B 测试切换。

    注：Field 的 description 会被工具（如 FastAPI / 自动文档工具）用于生成说明文档。
    """

    id: str = Field(
        ..., description=(
            "任务唯一 ID，推荐包含可读性强的命名，例如: 'weibo.user_feed:12345'，"
            "便于人工在日志/数据库中定位。"
        ),
    )

    collector_name: str = Field(
        ..., description=(
            "该任务使用的采集器名称（例如 'weibo.home'），调度器用此字段查找对应的 Collector 实现。"
        ),
    )

    interval_seconds: int = Field(
        ...,
        ge= -1,
        description=(
            "任务的调度间隔（秒）。若为 0 或负值，表示不做周期性调度（一次性任务）。"
        ),
    )

    enabled: bool = Field(
        True,
        description=(
            "布尔开关，表示任务是否启用；调度器在加载任务时应检查此字段，"
            "False 时可忽略或暂停该任务。"
        ),
    )


class TaskRunContext(BaseModel):
    """任务运行时上下文（TaskRunContext）。

    说明：
    - 本类用于一次任务执行期间携带的轻量上下文信息（用于日志、追踪、错误关联）。
    - 它与 TaskDefinition 是不同层级：TaskDefinition 描述任务静态配置，TaskRunContext 描述某次运行实例的元数据。

    字段详细说明：
    - task_id: 对应 TaskDefinition.id，用于将运行实例关联回静态定义，便于在日志/监控中交叉查询。
    - started_at: 本次运行的开始时间（UNIX 时间戳，单位：秒，浮点数允许子秒精度），便于计算运行耗时与判断超时。

    使用示例：
    >>> ctx = TaskRunContext(task_id="weibo.home", started_at=time.time())
    >>> logger.info("start job", task_id=ctx.task_id, ts=ctx.started_at)
    """

    task_id: str = Field(
        ...,
        description=(
            "对应 TaskDefinition.id 的字符串，用于把运行实例和静态定义关联合并便于追踪。"
        ),
    )

    started_at: float = Field(
        ...,
        description=(
            "本次运行的启动时间戳（UNIX epoch，以秒为单位，浮点数允许毫秒/微秒精度）。"
        ),
    )
