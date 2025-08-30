"""业务逻辑服务层

本模块实现了资讯相关的业务逻辑，作为控制器和数据访问层之间的中间层。
"""

from __future__ import annotations

import math
from typing import List, Optional
from datetime import datetime

from ..api.repositories import ArticleRepository
from ..api.schemas import (
    ArticleFilters, 
    PaginatedArticlesResponse,
    ArticleResponse,
    ArticleDetailResponse,
    PaginationInfo,
    SourcesResponse,
    SourceStats
)
from ..models.info_item import RawInfoItem


class ArticleService:
    """资讯业务逻辑服务
    
    处理资讯相关的业务逻辑，包括数据转换、分页计算等。
    遵循单一职责原则，专注于业务逻辑处理。
    """
    
    def __init__(self, repository: Optional[ArticleRepository] = None):
        """初始化服务
        
        Args:
            repository: 数据访问层实例，如果为None则创建默认实例
        """
        self.repository = repository or ArticleRepository()
    
    def get_articles_paginated(
        self, 
        filters: ArticleFilters
    ) -> PaginatedArticlesResponse:
        """获取分页资讯列表
        
        Args:
            filters: 筛选和分页参数
            
        Returns:
            PaginatedArticlesResponse: 分页资讯响应
        """
        # 从数据访问层获取数据
        articles, total_count = self.repository.get_articles_paginated(filters)
        
        # 计算分页信息
        total_pages = math.ceil(total_count / filters.limit) if total_count > 0 else 1
        has_next = filters.page < total_pages
        has_prev = filters.page > 1
        
        # 转换为响应模型
        article_responses = [
            self._convert_to_article_response(article) 
            for article in articles
        ]
        
        pagination_info = PaginationInfo(
            current_page=filters.page,
            total_pages=total_pages,
            total_items=total_count,
            per_page=filters.limit,
            has_next=has_next,
            has_prev=has_prev
        )
        
        return PaginatedArticlesResponse(
            data=article_responses,
            pagination=pagination_info
        )
    
    def get_article_detail(self, post_id: str) -> Optional[ArticleDetailResponse]:
        """获取资讯详情
        
        Args:
            post_id: 资讯ID
            
        Returns:
            ArticleDetailResponse: 资讯详情响应，如果不存在则返回None
        """
        article = self.repository.get_article_by_id(post_id)
        if not article:
            return None
        
        return self._convert_to_article_detail_response(article)
    
    def search_articles(
        self, 
        search_query: str, 
        filters: ArticleFilters
    ) -> PaginatedArticlesResponse:
        """搜索资讯
        
        Args:
            search_query: 搜索关键词
            filters: 筛选和分页参数
            
        Returns:
            PaginatedArticlesResponse: 分页搜索结果
        """
        # 从数据访问层获取搜索结果
        articles, total_count = self.repository.search_articles(search_query, filters)
        
        # 计算分页信息
        total_pages = math.ceil(total_count / filters.limit) if total_count > 0 else 1
        has_next = filters.page < total_pages
        has_prev = filters.page > 1
        
        # 转换为响应模型
        article_responses = [
            self._convert_to_article_response(article) 
            for article in articles
        ]
        
        pagination_info = PaginationInfo(
            current_page=filters.page,
            total_pages=total_pages,
            total_items=total_count,
            per_page=filters.limit,
            has_next=has_next,
            has_prev=has_prev
        )
        
        return PaginatedArticlesResponse(
            data=article_responses,
            pagination=pagination_info
        )
    
    def get_sources_stats(self) -> SourcesResponse:
        """获取来源统计信息
        
        Returns:
            SourcesResponse: 来源统计响应
        """
        # 从数据访问层获取统计数据
        stats_data = self.repository.get_sources_stats()
        
        # 转换为响应模型
        source_stats = [
            SourceStats(
                name=stat['name'],
                display_name=stat['display_name'],
                count=stat['count'],
                latest_update=stat['latest_update']
            )
            for stat in stats_data
        ]
        
        return SourcesResponse(sources=source_stats)
    
    def _convert_to_article_response(self, article: RawInfoItem) -> ArticleResponse:
        """将数据库模型转换为API响应模型
        
        Args:
            article: 数据库模型
            
        Returns:
            ArticleResponse: API响应模型
        """
        return ArticleResponse(
            post_id=article.post_id,
            source=article.source,
            title=article.title,
            url=article.url,
            description=article.description,
            query=article.query,
            engine=article.engine,
            collected_at=article.collected_at,
            processed=article.processed
        )
    
    def _convert_to_article_detail_response(
        self, 
        article: RawInfoItem
    ) -> ArticleDetailResponse:
        """将数据库模型转换为详情API响应模型
        
        Args:
            article: 数据库模型
            
        Returns:
            ArticleDetailResponse: 详情API响应模型
        """
        return ArticleDetailResponse(
            post_id=article.post_id,
            source=article.source,
            title=article.title,
            url=article.url,
            description=article.description,
            query=article.query,
            engine=article.engine,
            raw_data=article.raw_data,
            collected_at=article.collected_at,
            processed=article.processed
        )