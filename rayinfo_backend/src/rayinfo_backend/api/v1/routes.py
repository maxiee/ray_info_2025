"""API v1 路由定义。

此模块包含 RayInfo API v1 版本提供的所有 FastAPI 路由端点。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas import (
    ArticleDetailResponse,
    ArticleFilters,
    BatchReadStatusRequest,
    BatchReadStatusResponse,
    PaginatedArticlesResponse,
    ReadStatusRequest,
    ReadStatusResponse,
    SourcesResponse,
)
from ..services import ArticleService, ReadStatusService
from ...utils.instance_id import instance_manager

router = APIRouter(prefix="/api/v1", tags=["articles"])


def get_article_service() -> ArticleService:
    """依赖注入：获取文章服务实例"""

    return ArticleService()


def get_read_status_service() -> ReadStatusService:
    """依赖注入：获取已读状态服务实例"""

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
    """获取分页资讯列表"""

    try:
        if instance_id:
            instance = instance_manager.get_instance(instance_id)
            if instance:
                source = instance.collector.name
                if instance.param:
                    query = instance.param
            else:
                raise HTTPException(
                    status_code=404, detail=f"采集器实例 {instance_id} 不存在"
                )

        filters = ArticleFilters(
            page=page,
            limit=limit,
            source=source,
            query=query,
            start_date=start_date,
            end_date=end_date,
            read_status=read_status,
        )

        result = service.get_articles_paginated(filters)
        return result

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取资讯列表失败: {exc}",
        ) from exc


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
    """切换资讯已读状态"""

    try:
        result = service.toggle_read_status(post_id, request)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"资讯 {post_id} 不存在",
            )
        return result

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新已读状态失败: {exc}",
        ) from exc


@router.get(
    "/articles/{post_id}/read-status",
    response_model=ReadStatusResponse,
    summary="获取资讯已读状态",
    description="获取单篇资讯的已读状态信息",
)
async def get_article_read_status(
    post_id: str, service: ReadStatusService = Depends(get_read_status_service)
):
    """获取资讯已读状态"""

    try:
        result = service.get_read_status(post_id)
        if not result:
            return ReadStatusResponse(
                post_id=post_id,
                is_read=False,
                read_at=None,
                updated_at=datetime.now(),
            )
        return result

    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取已读状态失败: {exc}",
        ) from exc


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
    """批量设置资讯已读状态"""

    try:
        result = service.batch_toggle_read_status(request)
        return result

    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量更新已读状态失败: {exc}",
        ) from exc


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
    """搜索资讯"""

    try:
        filters = ArticleFilters(
            page=page,
            limit=limit,
            source=source,
            query=None,
            start_date=start_date,
            end_date=end_date,
            read_status=None,
        )

        result = service.search_articles(q, filters)
        return result

    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索资讯失败: {exc}",
        ) from exc


@router.get(
    "/sources",
    response_model=SourcesResponse,
    summary="获取来源统计",
    description="获取所有资讯来源的统计信息，包括数量和最新更新时间",
)
async def get_sources_stats(
    service: ArticleService = Depends(get_article_service),
):
    """获取来源统计信息"""

    try:
        result = service.get_sources_stats()
        return result

    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取来源统计失败: {exc}",
        ) from exc


@router.get("/health", summary="健康检查", description="API健康状态检查")
async def health_check():
    """API 健康检查端点"""

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "v1",
    }


@router.get(
    "/articles/{post_id}",
    response_model=ArticleDetailResponse,
    summary="获取资讯详情",
    description="根据资讯ID获取详细信息，包含完整的原始数据",
)
async def get_article_detail(
    post_id: str, service: ArticleService = Depends(get_article_service)
):
    """获取资讯详情"""

    try:
        result = service.get_article_detail(post_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"资讯 {post_id} 不存在",
            )
        return result

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取资讯详情失败: {exc}",
        ) from exc


@router.get("/collectors", summary="按类型分组列出采集器")
async def list_collectors_by_type():
    """按采集器类型分组列出采集器实例。"""

    instances = instance_manager.list_all_instances()
    collectors_by_type: dict[str, dict[str, Any]] = {}

    for instance_id, instance_info in instances.items():
        collector_name = instance_info.collector_name

        if collector_name not in collectors_by_type:
            collectors_by_type[collector_name] = {
                "collector_name": collector_name,
                "display_name": _get_collector_display_name(collector_name),
                "total_instances": 0,
                "instances": [],
            }

        instance_payload = instance_info.to_dict()
        instance_payload.update(
            {
                "instance_id": instance_id,
                "display_name": _get_instance_display_name(
                    collector_name, instance_info.param
                ),
            }
        )

        collectors_by_type[collector_name]["instances"].append(instance_payload)
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
        return _get_collector_display_name(collector_name)
    return param
