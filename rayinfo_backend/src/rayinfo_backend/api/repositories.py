"""数据访问层实现

本模块实现了资讯数据的数据库访问层，使用 Repository 模式封装数据操作。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import func, desc, or_

from ..models.info_item import RawInfoItem, ArticleReadStatus, DatabaseManager
from ..api.schemas import ArticleFilters


class ArticleRepository:
    """资讯数据访问层

    使用 Repository 模式封装所有与资讯数据相关的数据库操作，
    提供统一的数据访问接口，便于单元测试和业务逻辑分离。
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """初始化数据访问层

        Args:
            db_manager: 数据库管理器实例，如果为None则使用默认实例
        """
        self.db_manager = db_manager or DatabaseManager.get_instance()

    def get_articles_paginated(
        self, filters: ArticleFilters
    ) -> Tuple[List[RawInfoItem], int]:
        """获取分页资讯列表

        Args:
            filters: 筛选和分页参数

        Returns:
            Tuple[List[RawInfoItem], int]: (资讯列表, 总数量)
        """
        with self.db_manager.get_session() as session:
            # 构建基础查询
            query = session.query(RawInfoItem)

            # 应用筛选条件
            query = self._apply_filters(query, filters)

            # 获取总数量
            total_count = query.count()

            # 应用分页和排序
            offset = (filters.page - 1) * filters.limit
            articles = (
                query.order_by(desc(RawInfoItem.collected_at))  # 按采集时间倒序
                .offset(offset)
                .limit(filters.limit)
                .all()
            )

            return articles, total_count

    def get_article_by_id(self, post_id: str) -> Optional[RawInfoItem]:
        """根据ID获取资讯详情

        Args:
            post_id: 资讯ID

        Returns:
            RawInfoItem: 资讯对象，如果不存在则返回None
        """
        with self.db_manager.get_session() as session:
            return (
                session.query(RawInfoItem)
                .filter(RawInfoItem.post_id == post_id)
                .first()
            )

    def search_articles(
        self, search_query: str, filters: ArticleFilters
    ) -> Tuple[List[RawInfoItem], int]:
        """搜索资讯

        Args:
            search_query: 搜索关键词
            filters: 筛选和分页参数

        Returns:
            Tuple[List[RawInfoItem], int]: (资讯列表, 总数量)
        """
        with self.db_manager.get_session() as session:
            # 构建搜索查询
            search_pattern = f"%{search_query}%"
            query = session.query(RawInfoItem).filter(
                or_(
                    RawInfoItem.title.ilike(search_pattern),
                    RawInfoItem.description.ilike(search_pattern),
                    RawInfoItem.query.ilike(search_pattern),
                )
            )

            # 应用其他筛选条件（除了query字段）
            query = self._apply_filters(query, filters, exclude_query=True)

            # 获取总数量
            total_count = query.count()

            # 应用分页和排序
            offset = (filters.page - 1) * filters.limit
            articles = (
                query.order_by(desc(RawInfoItem.collected_at))
                .offset(offset)
                .limit(filters.limit)
                .all()
            )

            return articles, total_count

    def get_sources_stats(self) -> List[Dict[str, Any]]:
        """获取来源统计信息

        Returns:
            List[Dict[str, Any]]: 来源统计列表
        """
        with self.db_manager.get_session() as session:
            # 按来源分组统计
            stats = (
                session.query(
                    RawInfoItem.source,
                    func.count(RawInfoItem.post_id).label("count"),
                    func.max(RawInfoItem.collected_at).label("latest_update"),
                )
                .group_by(RawInfoItem.source)
                .all()
            )

            # 转换为字典格式
            result = []
            for stat in stats:
                result.append(
                    {
                        "name": stat.source,
                        "display_name": self._get_display_name(stat.source),
                        "count": stat.count,
                        "latest_update": stat.latest_update,
                    }
                )

            return result

    def _apply_common_filters(
        self, query, filters: ArticleFilters, *, exclude_query: bool = False
    ):
        """应用通用筛选条件"""
        if filters.source:
            query = query.filter(RawInfoItem.source == filters.source)

        if filters.query and not exclude_query:
            query = query.filter(RawInfoItem.query == filters.query)

        if filters.start_date:
            query = query.filter(RawInfoItem.collected_at >= filters.start_date)

        if filters.end_date:
            query = query.filter(RawInfoItem.collected_at <= filters.end_date)

        return query

    def _apply_filters(
        self, query, filters: ArticleFilters, exclude_query: bool = False
    ):
        """应用筛选条件到原始资讯查询"""
        query = self._apply_common_filters(query, filters, exclude_query=exclude_query)

        if filters.read_status and filters.read_status != "all":
            # read_status 依赖已读状态表的 join，保持与当前调用路径兼容
            pass

        return query

    def _get_display_name(self, source: str) -> str:
        """获取来源的显示名称

        Args:
            source: 来源标识

        Returns:
            str: 显示名称
        """
        display_names = {
            "mes.search": "搜索引擎",
            "weibo.home": "微博首页",
            "rss.feed": "RSS订阅",
        }
        return display_names.get(source, source)

    # 已读状态相关方法

    def update_read_status(self, post_id: str, is_read: bool) -> ArticleReadStatus:
        """更新资讯的已读状态

        Args:
            post_id: 资讯ID
            is_read: 是否已读

        Returns:
            ArticleReadStatus: 更新后的已读状态对象
        """
        with self.db_manager.get_session() as session:
            # 查找现有的已读状态记录
            read_status = (
                session.query(ArticleReadStatus)
                .filter(ArticleReadStatus.post_id == post_id)
                .first()
            )

            current_time = datetime.utcnow()

            if read_status:
                # 更新现有记录
                read_status.is_read = is_read
                read_status.read_at = current_time if is_read else None
                read_status.updated_at = current_time
            else:
                # 创建新记录
                read_status = ArticleReadStatus(
                    post_id=post_id,
                    is_read=is_read,
                    read_at=current_time if is_read else None,
                    updated_at=current_time,
                )
                session.add(read_status)

            session.commit()
            session.refresh(read_status)
            return read_status

    def get_read_status(self, post_id: str) -> Optional[ArticleReadStatus]:
        """获取资讯的已读状态

        Args:
            post_id: 资讯ID

        Returns:
            ArticleReadStatus: 已读状态对象，如果不存在则返回None
        """
        with self.db_manager.get_session() as session:
            return (
                session.query(ArticleReadStatus)
                .filter(ArticleReadStatus.post_id == post_id)
                .first()
            )

    def get_articles_with_read_status(
        self, filters: ArticleFilters
    ) -> Tuple[List[Tuple[RawInfoItem, Optional[ArticleReadStatus]]], int]:
        """获取带已读状态的分页资讯列表

        Args:
            filters: 筛选和分页参数

        Returns:
            Tuple[List[Tuple[RawInfoItem, Optional[ArticleReadStatus]]], int]: (资讯和已读状态列表, 总数量)
        """
        with self.db_manager.get_session() as session:
            # 构建基础查询，左连接已读状态表
            query = session.query(RawInfoItem, ArticleReadStatus).outerjoin(
                ArticleReadStatus, RawInfoItem.post_id == ArticleReadStatus.post_id
            )

            # 应用筛选条件
            query = self._apply_filters_with_read_status(query, filters)

            # 获取总数量
            total_count = query.count()

            # 应用分页和排序
            offset = (filters.page - 1) * filters.limit
            results = (
                query.order_by(desc(RawInfoItem.collected_at))
                .offset(offset)
                .limit(filters.limit)
                .all()
            )

            return results, total_count

    def _apply_filters_with_read_status(
        self, query, filters: ArticleFilters, exclude_query: bool = False
    ):
        """应用筛选条件到带已读状态的查询

        Args:
            query: SQLAlchemy查询对象
            filters: 筛选参数
            exclude_query: 是否排除query字段筛选

        Returns:
            应用筛选后的查询对象
        """
        query = self._apply_common_filters(query, filters, exclude_query=exclude_query)

        # 已读状态筛选
        if filters.read_status:
            if filters.read_status == "read":
                query = query.filter(ArticleReadStatus.is_read == True)
            elif filters.read_status == "unread":
                query = query.filter(
                    or_(
                        ArticleReadStatus.is_read == False,
                        ArticleReadStatus.is_read.is_(None),
                    )
                )
            # 'all' 或其他值不做筛选

        return query
