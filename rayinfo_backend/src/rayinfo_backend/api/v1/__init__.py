"""API v1 路由控制器

本模块实现了 RayInfo API v1 版本的所有路由端点。
"""

from __future__ import annotations

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends, status
from fastapi.responses import JSONResponse

from ..services import ArticleService
from ..schemas import (
    PaginatedArticlesResponse,
    ArticleDetailResponse,
    SourcesResponse,
    ArticleFilters,
    ErrorResponse
)

# 创建路由器
router = APIRouter(prefix="/api/v1", tags=["articles"])

# 依赖注入：获取服务实例
def get_article_service() -> ArticleService:
    """获取文章服务实例（依赖注入）"""
    return ArticleService()


@router.get(
    "/articles",
    response_model=PaginatedArticlesResponse,
    summary="获取资讯列表",
    description="获取分页的资讯列表，支持来源筛选、关键词筛选和日期范围筛选"
)
async def get_articles(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页条数"),
    source: Optional[str] = Query(None, description="来源筛选"),
    query: Optional[str] = Query(None, description="关键词筛选"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    service: ArticleService = Depends(get_article_service)
):
    """获取分页资讯列表
    
    支持的筛选参数：
    - source: 按来源筛选 (如: mes.search, weibo.home)
    - query: 按关键词筛选
    - start_date/end_date: 按日期范围筛选
    
    Returns:
        PaginatedArticlesResponse: 分页资讯数据
    """
    try:
        # 构建筛选参数
        filters = ArticleFilters(
            page=page,
            limit=limit,
            source=source,
            query=query,
            start_date=start_date,
            end_date=end_date
        )
        
        # 获取分页数据
        result = service.get_articles_paginated(filters)
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取资讯列表失败: {str(e)}"
        )


@router.get(
    "/articles/{post_id}",
    response_model=ArticleDetailResponse,
    summary="获取资讯详情",
    description="根据资讯ID获取详细信息，包含完整的原始数据"
)
async def get_article_detail(
    post_id: str,
    service: ArticleService = Depends(get_article_service)
):
    """获取资讯详情
    
    Args:
        post_id: 资讯唯一标识符
        
    Returns:
        ArticleDetailResponse: 资讯详情数据
        
    Raises:
        HTTPException: 当资讯不存在时返回404错误
    """
    try:
        result = service.get_article_detail(post_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"资讯 {post_id} 不存在"
            )
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取资讯详情失败: {str(e)}"
        )


@router.get(
    "/search",
    response_model=PaginatedArticlesResponse,
    summary="搜索资讯",
    description="根据关键词搜索资讯，支持标题、描述和查询字段的模糊匹配"
)
async def search_articles(
    q: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页条数"),
    source: Optional[str] = Query(None, description="来源筛选"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    service: ArticleService = Depends(get_article_service)
):
    """搜索资讯
    
    支持搜索的字段：
    - title: 资讯标题
    - description: 资讯描述
    - query: 搜索关键词
    
    Args:
        q: 搜索关键词
        page: 页码
        limit: 每页条数
        source: 来源筛选
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        PaginatedArticlesResponse: 搜索结果
    """
    try:
        # 构建筛选参数（不包含query字段，避免冲突）
        filters = ArticleFilters(
            page=page,
            limit=limit,
            source=source,
            start_date=start_date,
            end_date=end_date
        )
        
        # 执行搜索
        result = service.search_articles(q, filters)
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索资讯失败: {str(e)}"
        )


@router.get(
    "/sources",
    response_model=SourcesResponse,
    summary="获取来源统计",
    description="获取所有资讯来源的统计信息，包括数量和最新更新时间"
)
async def get_sources_stats(
    service: ArticleService = Depends(get_article_service)
):
    """获取来源统计信息
    
    Returns:
        SourcesResponse: 来源统计数据
    """
    try:
        result = service.get_sources_stats()
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取来源统计失败: {str(e)}"
        )


@router.get(
    "/health",
    summary="健康检查",
    description="API健康状态检查"
)
async def health_check():
    """API健康检查端点
    
    Returns:
        dict: 健康状态信息
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "v1"
    }