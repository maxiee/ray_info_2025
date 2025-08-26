"""管道处理工具模块

本模块包含数据转换和验证相关的工具类。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from ..collectors.base import RawEvent
from ..models.info_item import RawInfoItem


class DataTransformer:
    """数据转换器

    负责将RawEvent转换为数据库实体对象。
    分离数据转换逻辑，提升可测试性。
    """

    @staticmethod
    def transform_event_to_item(event: RawEvent) -> RawInfoItem:
        """将RawEvent转换为RawInfoItem

        Args:
            event: 原始事件

        Returns:
            数据库实体对象
        """
        raw_data = event.raw

        return RawInfoItem(
            post_id=raw_data.get("post_id")
            or DataTransformer._generate_fallback_id(raw_data),
            source=event.source,
            title=raw_data.get("title"),
            url=raw_data.get("url"),
            description=raw_data.get("description"),
            query=raw_data.get("query"),
            engine=raw_data.get("engine"),
            raw_data=raw_data,
            collected_at=datetime.utcnow(),
            processed=0,
        )

    @staticmethod
    def _generate_fallback_id(raw_data: dict) -> str:
        """为缺少 post_id 的数据生成后备 ID

        Args:
            raw_data: 原始数据字典

        Returns:
            生成的唯一 ID
        """
        # 使用原始数据的哈希值作为后备 ID
        data_str = json.dumps(raw_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode()).hexdigest()


class EventValidator:
    """事件验证器

    负责验证事件数据的有效性。
    """

    @staticmethod
    def validate_event(event: RawEvent) -> tuple[bool, str | None]:
        """验证事件数据

        Args:
            event: 要验证的事件

        Returns:
            tuple[bool, str | None]: (是否有效, 错误信息)
        """
        if not event.source:
            return False, "source 字段不能为空"

        if not isinstance(event.raw, dict):
            return False, "raw 字段必须是字典类型"

        if not event.raw:
            return False, "raw 字段不能为空"

        return True, None
