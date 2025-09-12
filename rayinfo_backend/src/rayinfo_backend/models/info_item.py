"""信息条目数据模型

本模块定义了用于存储原始信息条目的数据模型，使用 SQLAlchemy ORM 实现。
支持多种信息源（搜索引擎、微博、RSS等）的统一存储。
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional
import threading

from sqlalchemy import (
    String,
    Text,
    DateTime,
    Integer,
    JSON,
    Float,
    Boolean,
    ForeignKey,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
)


# SQLAlchemy 基类（Typed Declarative）
class Base(DeclarativeBase):
    pass


class CollectorExecutionState(Base):
    """采集器/任务执行状态表

    用于存储每个任务的最后执行时间，实现智能调度功能。
    支持普通任务和参数化任务两种模式。

    字段说明：
    - collector_name: 任务源名称（如 weibo.home）
    - param_key: 参数键，用于区分参数化任务的不同实例
    - last_execution_time: 最后执行时间戳（Unix时间戳）
    - created_at: 创建时间
    - updated_at: 更新时间
    - execution_count: 执行次数统计
    """

    __tablename__ = "collector_execution_state"

    # 复合主键：任务源名称 + 参数键
    collector_name: Mapped[str] = mapped_column(
        String, primary_key=True, comment="任务源名称，如 weibo.home"
    )
    param_key: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        nullable=False,  # 不允许NULL，普通任务使用空字符串
        default="",  # 默认为空字符串
        comment="参数键，普通任务为空字符串",
    )

    # 时间戳字段
    last_execution_time: Mapped[float] = mapped_column(
        Float, nullable=False, index=True, comment="最后执行时间戳（Unix时间戳）"
    )
    created_at: Mapped[float] = mapped_column(
        Float, nullable=False, comment="创建时间戳"
    )
    updated_at: Mapped[float] = mapped_column(
        Float, nullable=False, comment="更新时间戳"
    )

    # 统计字段
    execution_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="执行次数统计"
    )

    def __repr__(self) -> str:
        return (
            f"<CollectorExecutionState("
            f"collector_name={self.collector_name}, "
            f"param_key={self.param_key}, "
            f"execution_count={self.execution_count})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "collector_name": self.collector_name,
            "param_key": self.param_key,
            "last_execution_time": self.last_execution_time,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "execution_count": self.execution_count,
        }


class ScheduledTask(Base):
    """调度任务表

    用于持久化调度器中的待执行任务，实现断点续传功能。
    存储任务的完整信息，支持冷启动时恢复任务队列。

    字段说明：
    - uuid: 任务唯一标识符，主键
    - source: 任务源名称
    - args: 任务参数（JSON格式）
    - schedule_at: 计划执行时间
    - interval: 重复间隔秒数（可选）
    - status: 任务状态（pending/running/completed/failed）
    - created_at: 创建时间
    - updated_at: 更新时间
    """

    __tablename__ = "scheduled_tasks"

    # 主键
    uuid: Mapped[str] = mapped_column(
        String, primary_key=True, comment="任务唯一标识符"
    )

    # 任务基本信息
    source: Mapped[str] = mapped_column(
        String, nullable=False, index=True, comment="任务源名称"
    )
    args: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=lambda: {}, comment="任务参数（JSON格式）"
    )

    # 调度信息
    schedule_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, comment="计划执行时间"
    )
    interval: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="重复间隔秒数（可选）"
    )

    # 状态信息
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending",
        index=True,
        comment="任务状态：pending/running/completed/failed",
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return (
            f"<ScheduledTask("
            f"uuid={self.uuid[:8]}, "
            f"source={self.source}, "
            f"status={self.status}, "
            f"schedule_at={self.schedule_at})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "uuid": self.uuid,
            "source": self.source,
            "args": self.args,
            "schedule_at": (
                self.schedule_at.isoformat() if self.schedule_at is not None else None
            ),
            "interval": self.interval,
            "status": self.status,
            "created_at": (
                self.created_at.isoformat() if self.created_at is not None else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at is not None else None
            ),
        }


class RawInfoItem(Base):
    """原始信息条目表

    用于存储从各种信息源采集到的原始数据，包括搜索引擎结果、
    微博内容、RSS 文章等。支持去重、富化和后续处理。

    字段说明：
    - post_id: 主键，用于去重的唯一标识符
    - source: 信息来源标识（如 mes.search, weibo.home）
    - title: 信息标题
    - url: 信息链接
    - description: 信息描述/摘要
    - query: 搜索关键词（对搜索引擎采集器）
    - engine: 搜索引擎名称
    - raw_data: 完整的原始数据（JSON 格式）
    - collected_at: 采集时间
    - processed: 处理状态（0=未处理，1=已处理，-1=处理失败）
    """

    __tablename__ = "raw_info_items"

    # 主键：使用采集器提供的 post_id 作为去重键
    post_id: Mapped[str] = mapped_column(
        String, primary_key=True, comment="唯一标识符，用于去重"
    )

    # 基础字段
    source: Mapped[str] = mapped_column(
        String, nullable=False, index=True, comment="信息来源标识"
    )
    title: Mapped[Optional[str]] = mapped_column(Text, comment="信息标题")
    url: Mapped[Optional[str]] = mapped_column(Text, comment="信息链接")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="信息描述或摘要")

    # 采集相关字段
    query: Mapped[Optional[str]] = mapped_column(
        String, index=True, comment="搜索关键词（搜索引擎采集器使用）"
    )
    engine: Mapped[Optional[str]] = mapped_column(String, comment="搜索引擎名称")

    # 元数据
    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, comment="完整的原始数据"
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, comment="采集时间"
    )

    # 处理状态
    processed: Mapped[int] = mapped_column(
        Integer, default=0, index=True, comment="处理状态：0=未处理，1=已处理，-1=失败"
    )

    def __repr__(self) -> str:
        title_preview = (self.title or "")[:50]
        return f"<RawInfoItem(post_id={self.post_id}, source={self.source}, title={title_preview}...)>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "post_id": self.post_id,
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "description": self.description,
            "query": self.query,
            "engine": self.engine,
            "raw_data": self.raw_data,
            "collected_at": (
                self.collected_at.isoformat() if self.collected_at is not None else None
            ),
            "processed": self.processed,
        }


class ArticleReadStatus(Base):
    """资讯已读状态表

    用于存储用户对资讯的已读状态，支持手动标记已读/未读。

    字段说明：
    - post_id: 外键，关联到 raw_info_items 表的 post_id
    - is_read: 已读状态，默认为 False
    - read_at: 标记已读的时间戳，未读时为 None
    - updated_at: 最后更新时间
    """

    __tablename__ = "article_read_status"

    # 主键：使用 post_id 作为主键，与 raw_info_items 一对一关联
    post_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("raw_info_items.post_id", ondelete="CASCADE"),
        primary_key=True,
        comment="资讯唯一标识符，外键关联到raw_info_items表",
    )

    # 已读状态
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="已读状态：True=已读，False=未读",
    )

    # 时间戳字段
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True, comment="标记已读的时间戳，未读时为None"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="最后更新时间",
    )

    def __repr__(self) -> str:
        return (
            f"<ArticleReadStatus("
            f"post_id={self.post_id}, "
            f"is_read={self.is_read}, "
            f"read_at={self.read_at})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "post_id": self.post_id,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at is not None else None,
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at is not None else None
            ),
        }


class DatabaseManager:
    """数据库管理器（单例模式）

    提供数据库连接和会话管理功能，支持自动创建表结构。
    采用线程安全的单例模式，确保全局只有一个数据库管理器实例。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = "rayinfo.db"):
        """单例模式实现

        Args:
            db_path: SQLite 数据库文件路径

        Returns:
            DatabaseManager: 单例实例
        """
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = "rayinfo.db"):
        """初始化数据库管理器

        Args:
            db_path: SQLite 数据库文件路径
        """
        # 确保只初始化一次
        if self._initialized:
            return

        self.db_path = db_path
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            # SQLite 优化配置
            connect_args={"check_same_thread": False},
            echo=False,  # 设为 True 可查看 SQL 语句
        )
        # 线程安全地创建表结构
        with self.__class__._lock:
            Base.metadata.create_all(self.engine, checkfirst=True)
        # 创建会话工厂
        self.Session = sessionmaker(bind=self.engine)

        self._initialized = True

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def create_tables(self):
        """创建所有表结构"""
        Base.metadata.create_all(self.engine)

        # 为collector_execution_state表创建索引以优化查询性能
        try:
            from sqlalchemy import text

            with self.engine.connect() as conn:
                # 检查索引是否存在，避免重复创建
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_collector_execution_time "
                        "ON collector_execution_state(collector_name, last_execution_time)"
                    )
                )

                # 为article_read_status表创建索引
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_article_read_status_is_read "
                        "ON article_read_status(is_read)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_article_read_status_read_at "
                        "ON article_read_status(read_at)"
                    )
                )

                conn.commit()
        except Exception as e:
            # 如果索引已存在或创建失败，记录但不中断
            pass

    def drop_tables(self):
        """删除所有表结构（慎用）"""
        Base.metadata.drop_all(self.engine)

    @classmethod
    def reset_instance(cls):
        """重置单例实例（主要用于测试）

        注意：这个方法应该谨慎使用，主要用于单元测试中重置状态。
        """
        with cls._lock:
            cls._instance = None

    @classmethod
    def get_instance(cls, db_path: str = "rayinfo.db") -> "DatabaseManager":
        """获取单例实例的便捷方法

        Args:
            db_path: SQLite 数据库文件路径

        Returns:
            DatabaseManager: 单例实例
        """
        return cls(db_path)
