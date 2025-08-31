"""API 响应模型定义

本模块定义了 RayInfo API 的请求和响应模型，使用 Pydantic 实现数据验证和序列化。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ArticleBase(BaseModel):
    """资讯基础模型"""
    post_id: str = Field(..., description="资讯唯一标识符")
    source: str = Field(..., description="信息来源标识")
    title: Optional[str] = Field(None, description="资讯标题")
    url: Optional[str] = Field(None, description="资讯链接")
    description: Optional[str] = Field(None, description="资讯描述")
    query: Optional[str] = Field(None, description="搜索关键词")
    engine: Optional[str] = Field(None, description="搜索引擎名称")
    collected_at: datetime = Field(..., description="采集时间")
    processed: int = Field(0, description="处理状态")


class ArticleResponse(ArticleBase):
    """资讯响应模型（列表项）"""
    
    class Config:
        from_attributes = True


class ArticleDetailResponse(ArticleBase):
    """资讯详情响应模型"""
    raw_data: Optional[Dict[str, Any]] = Field(None, description="原始数据")
    
    class Config:
        from_attributes = True


class PaginationInfo(BaseModel):
    """分页信息模型"""
    current_page: int = Field(..., description="当前页码")
    total_pages: int = Field(..., description="总页数")
    total_items: int = Field(..., description="总条目数")
    per_page: int = Field(..., description="每页条数")
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")


class PaginatedArticlesResponse(BaseModel):
    """分页资讯响应模型"""
    data: List[ArticleResponse] = Field(..., description="资讯列表")
    pagination: PaginationInfo = Field(..., description="分页信息")


class SourceStats(BaseModel):
    """来源统计模型"""
    name: str = Field(..., description="来源名称")
    display_name: str = Field(..., description="显示名称")
    count: int = Field(..., description="资讯数量")
    latest_update: Optional[datetime] = Field(None, description="最新更新时间")


class SourcesResponse(BaseModel):
    """来源统计响应模型"""
    sources: List[SourceStats] = Field(..., description="来源列表")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细信息")


class ArticleFilters(BaseModel):
    """资讯筛选参数模型"""
    page: int = Field(1, ge=1, description="页码")
    limit: int = Field(20, ge=1, le=100, description="每页条数")
    source: Optional[str] = Field(None, description="来源筛选")
    query: Optional[str] = Field(None, description="关键词搜索") 
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    read_status: Optional[str] = Field(None, description="已读状态筛选：read, unread, all")


# 已读状态相关模型
class ReadStatusRequest(BaseModel):
    """已读状态请求模型"""
    is_read: bool = Field(..., description="是否已读：True=已读，False=未读")


class BatchReadStatusRequest(BaseModel):
    """批量已读状态请求模型"""
    post_ids: List[str] = Field(..., description="资讯ID列表")
    is_read: bool = Field(..., description="是否已读：True=已读，False=未读")


class ReadStatusResponse(BaseModel):
    """已读状态响应模型"""
    post_id: str = Field(..., description="资讯ID")
    is_read: bool = Field(..., description="是否已读")
    read_at: Optional[datetime] = Field(None, description="标记已读时间")
    updated_at: datetime = Field(..., description="最后更新时间")
    
    class Config:
        from_attributes = True


class BatchReadStatusResponse(BaseModel):
    """批量已读状态响应模型"""
    success_count: int = Field(..., description="成功处理的数量")
    failed_count: int = Field(..., description="失败数量")
    results: List[ReadStatusResponse] = Field(..., description="处理结果详情")


class ArticleWithReadStatus(ArticleBase):
    """带已读状态的资讯模型"""
    is_read: bool = Field(False, description="是否已读")
    read_at: Optional[datetime] = Field(None, description="标记已读时间")
    
    class Config:
        from_attributes = True