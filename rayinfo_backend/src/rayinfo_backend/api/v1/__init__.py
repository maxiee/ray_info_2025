"""API v1 路由控制器

本模块实现了 RayInfo API v1 版本的所有路由端点。
"""

from __future__ import annotations

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends, status, Path
from fastapi.responses import JSONResponse

from ..services import ArticleService, ReadStatusService
from ..schemas import (
    PaginatedArticlesResponse,
    ArticleDetailResponse,
    SourcesResponse,
    ArticleFilters,
    ErrorResponse,
    ReadStatusRequest,
    ReadStatusResponse,
    BatchReadStatusRequest,
    BatchReadStatusResponse,
    ArticleWithReadStatus,
)
from ...utils.instance_id import instance_manager

# 创建路由器
router = APIRouter(prefix="/api/v1", tags=["articles"])


# 依赖注入：获取服务实例
def get_article_service() -> ArticleService:
    """获取文章服务实例（依赖注入）"""
    return ArticleService()


def get_read_status_service() -> ReadStatusService:
    """获取已读状态服务实例（依赖注入）"""
    return ReadStatusService()


@router.get(
    "/articles",
    response_model=PaginatedArticlesResponse,
    summary="获取资讯列表",
    description="获取分页的资讯列表，支持来源筛选、实例ID筛选、关键词筛选和日期范围筛选",
)
async def get_articles(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页条数"),
    source: Optional[str] = Query(None, description="来源筛选"),
    instance_id: Optional[str] = Query(None, description="采集器实例ID筛选"),
    query: Optional[str] = Query(None, description="关键词筛选"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    read_status: Optional[str] = Query(
        None, description="已读状态筛选：read, unread, all"
    ),
    service: ArticleService = Depends(get_article_service),
):
    """获取分页资讯列表

    支持的筛选参数：
    - source: 按来源筛选 (如: mes.search, weibo.home)
    - instance_id: 按采集器实例ID筛选，会自动解析为对应的采集器和参数
    - query: 按关键词筛选
    - start_date/end_date: 按日期范围筛选

    Returns:
        PaginatedArticlesResponse: 分页资讯数据
    """
    try:
        # 如果提供了instance_id，解析为对应的source和query参数
        if instance_id:
            from ...utils.instance_id import instance_manager

            instance = instance_manager.get_instance(instance_id)
            if instance:
                source = instance.collector.name
                # 对于参数化采集器，使用参数作为query过滤条件
                if instance.param:
                    query = instance.param
            else:
                raise HTTPException(
                    status_code=404, detail=f"采集器实例 {instance_id} 不存在"
                )

        # 构建筛选参数
        filters = ArticleFilters(
            page=page,
            limit=limit,
            source=source,
            query=query,
            start_date=start_date,
            end_date=end_date,
            read_status=read_status,
        )

        # 获取分页数据
        result = service.get_articles_paginated(filters)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取资讯列表失败: {str(e)}",
        )


# 已读状态相关路由（必须在 {post_id:path} 路由之前定义）
@router.put(
    "/articles/{post_id}/read-status",
    response_model=ReadStatusResponse,
    summary="切换资讯已读状态",
    description="手动切换单篇资讯的已读/未读状态",
)
async def toggle_article_read_status(
    post_id: str,
    request: ReadStatusRequest,
    service: ReadStatusService = Depends(get_read_status_service),
):
    """切换资讯已读状态

    Args:
        post_id: 资讯唯一标识符（UUID格式）
        request: 已读状态请求数据

    Returns:
        ReadStatusResponse: 更新后的已读状态

    Raises:
        HTTPException: 当资讯不存在时返回404错误
    """
    try:
        result = service.toggle_read_status(post_id, request)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"资讯 {post_id} 不存在"
            )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新已读状态失败: {str(e)}",
        )


@router.get(
    "/articles/{post_id}/read-status",
    response_model=ReadStatusResponse,
    summary="获取资讯已读状态",
    description="获取单篇资讯的已读状态信息",
)
async def get_article_read_status(
    post_id: str, service: ReadStatusService = Depends(get_read_status_service)
):
    """获取资讯已读状态

    Args:
        post_id: 资讯唯一标识符（UUID格式）

    Returns:
        ReadStatusResponse: 已读状态信息

    Raises:
        HTTPException: 当资讯不存在时返回404错误
    """
    try:
        result = service.get_read_status(post_id)
        if not result:
            # 如果没有已读状态记录，返回默认未读状态
            return ReadStatusResponse(
                post_id=post_id, is_read=False, read_at=None, updated_at=datetime.now()
            )
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取已读状态失败: {str(e)}",
        )


@router.put(
    "/articles/batch-read-status",
    response_model=BatchReadStatusResponse,
    summary="批量设置资讯已读状态",
    description="批量设置多篇资讯的已读/未读状态",
)
async def batch_toggle_read_status(
    request: BatchReadStatusRequest,
    service: ReadStatusService = Depends(get_read_status_service),
):
    """批量设置资讯已读状态

    Args:
        request: 批量已读状态请求数据

    Returns:
        BatchReadStatusResponse: 批量操作结果
    """
    try:
        result = service.batch_toggle_read_status(request)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量更新已读状态失败: {str(e)}",
        )


@router.get(
    "/search",
    response_model=PaginatedArticlesResponse,
    summary="搜索资讯",
    description="根据关键词搜索资讯，支持标题、描述和查询字段的模糊匹配",
)
async def search_articles(
    q: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页条数"),
    source: Optional[str] = Query(None, description="来源筛选"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    service: ArticleService = Depends(get_article_service),
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
            query=None,  # 搜索接口不使用query字段筛选
            start_date=start_date,
            end_date=end_date,
            read_status=None,  # 搜索接口不筛选已读状态
        )

        # 执行搜索
        result = service.search_articles(q, filters)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索资讯失败: {str(e)}",
        )


@router.get(
    "/sources",
    response_model=SourcesResponse,
    summary="获取来源统计",
    description="获取所有资讯来源的统计信息，包括数量和最新更新时间",
)
async def get_sources_stats(service: ArticleService = Depends(get_article_service)):
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
            detail=f"获取来源统计失败: {str(e)}",
        )


@router.get("/health", summary="健康检查", description="API健康状态检查")
async def health_check():
    """API健康检查端点

    Returns:
        dict: 健康状态信息
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "v1",
    }


# 资讯详情路由
@router.get(
    "/articles/{post_id}",
    response_model=ArticleDetailResponse,
    summary="获取资讯详情",
    description="根据资讯ID获取详细信息，包含完整的原始数据",
)
async def get_article_detail(
    post_id: str, service: ArticleService = Depends(get_article_service)
):
    """获取资讯详情

    Args:
        post_id: 资讯唯一标识符（UUID格式）

    Returns:
        ArticleDetailResponse: 资讯详情数据

    Raises:
        HTTPException: 当资讯不存在时返回404错误
    """
    try:
        result = service.get_article_detail(post_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"资讯 {post_id} 不存在"
            )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取资讯详情失败: {str(e)}",
        )


# 采集器相关API


@router.get("/collectors", summary="按类型分组列出采集器")
async def list_collectors_by_type():
    """按采集器类型分组列出采集器实例。

    Returns:
        dict: 按采集器类型分组的实例信息
    """
    instances = instance_manager.list_all_instances()
    collectors_by_type = {}

    for instance_id, instance_info in instances.items():
        collector_name = instance_info["collector_name"]

        if collector_name not in collectors_by_type:
            collectors_by_type[collector_name] = {
                "collector_name": collector_name,
                "display_name": _get_collector_display_name(collector_name),
                "total_instances": 0,
                "instances": [],
            }

        # 添加实例信息
        instance_detail = {
            "instance_id": instance_id,
            "param": instance_info.get("param"),
            "display_name": _get_instance_display_name(
                collector_name, instance_info.get("param")
            ),
            "status": instance_info.get("status"),
            "health_score": instance_info.get("health_score"),
            "run_count": instance_info.get("run_count", 0),
            "error_count": instance_info.get("error_count", 0),
            "last_run": instance_info.get("last_run"),
            "created_at": instance_info.get("created_at"),
        }

        collectors_by_type[collector_name]["instances"].append(instance_detail)
        collectors_by_type[collector_name]["total_instances"] += 1

    return {
        "total_collectors": len(collectors_by_type),
        "collectors": collectors_by_type,
    }


def _get_collector_display_name(collector_name: str) -> str:
    """获取采集器的显示名称"""
    display_names = {
        "mes.search": "搜索引擎",
        "weibo.home": "微博首页",
        "rss.feed": "RSS订阅",
    }
    return display_names.get(collector_name, collector_name)


def _get_instance_display_name(collector_name: str, param: str | None) -> str:
    """获取实例的显示名称"""
    if param is None:
        # 普通采集器，使用采集器名称
        return _get_collector_display_name(collector_name)
    else:
        # 参数化采集器，使用参数作为显示名称
        return param
