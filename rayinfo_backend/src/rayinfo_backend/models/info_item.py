"""信息条目数据模型

本模块定义了用于存储原始信息条目的数据模型，使用 SQLAlchemy ORM 实现。
支持多种信息源（搜索引擎、微博、RSS等）的统一存储。
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLAlchemy 基类
Base = declarative_base()


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
    post_id = Column(String, primary_key=True, comment="唯一标识符，用于去重")

    # 基础字段
    source = Column(String, nullable=False, index=True, comment="信息来源标识")
    title = Column(Text, comment="信息标题")
    url = Column(Text, comment="信息链接")
    description = Column(Text, comment="信息描述或摘要")

    # 采集相关字段
    query = Column(String, index=True, comment="搜索关键词（搜索引擎采集器使用）")
    engine = Column(String, comment="搜索引擎名称")

    # 元数据
    raw_data = Column(JSON, comment="完整的原始数据")
    collected_at = Column(
        DateTime, default=datetime.utcnow, index=True, comment="采集时间"
    )

    # 处理状态
    processed = Column(
        Integer, default=0, index=True, comment="处理状态：0=未处理，1=已处理，-1=失败"
    )

    def __repr__(self) -> str:
        return f"<RawInfoItem(post_id={self.post_id}, source={self.source}, title={self.title[:50]}...)>"

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


class DatabaseManager:
    """数据库管理器

    提供数据库连接和会话管理功能，支持自动创建表结构。
    """

    def __init__(self, db_path: str = "rayinfo.db"):
        """初始化数据库管理器

        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            # SQLite 优化配置
            connect_args={"check_same_thread": False},
            echo=False,  # 设为 True 可查看 SQL 语句
        )
        # 创建表结构
        Base.metadata.create_all(self.engine)
        # 创建会话工厂
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def create_tables(self):
        """创建所有表结构"""
        Base.metadata.create_all(self.engine)

    def drop_tables(self):
        """删除所有表结构（慎用）"""
        Base.metadata.drop_all(self.engine)
