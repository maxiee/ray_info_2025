"""去重处理阶段模块

本模块包含数据去重相关的管道阶段实现。
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any, Dict

from ..collectors.base import RawEvent
from .stage_base import PipelineStage


class DedupStage(PipelineStage):
    """优化的去重处理阶段

    使用集合和LRU缓存机制提供高效的去重处理。
    相比原有的列表实现，性能提升显著（O(1) vs O(n)）。
    """

    def __init__(self, max_size: int = 1000, use_content_hash: bool = False):
        """初始化去重阶段

        Args:
            max_size: LRU缓存最大大小，防止内存无限增长
            use_content_hash: 是否使用内容哈希作为去重键（更准确但性能较低）
        """
        super().__init__("DedupStage")
        self.max_size = max_size
        self.use_content_hash = use_content_hash

        # 使用OrderedDict实现LRU缓存
        self._seen_cache: OrderedDict[str, bool] = OrderedDict()

        # 去重统计
        self._dedup_stats = {
            "total_input": 0,
            "duplicates_found": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    def _generate_dedup_key(self, event: RawEvent) -> str:
        """生成去重键

        Args:
            event: 要处理的事件

        Returns:
            去重键字符串
        """
        # 优先使用post_id
        post_id = event.raw.get("post_id")
        if post_id:
            return f"pid:{post_id}"

        # 其次使用URL
        url = event.raw.get("url")
        if url:
            return f"url:{url}"

        # 如果启用内容哈希，对整个内容生成哈希
        if self.use_content_hash:
            try:
                content_str = json.dumps(event.raw, sort_keys=True, ensure_ascii=False)
                hash_obj = hashlib.md5(content_str.encode("utf-8"))
                return f"hash:{hash_obj.hexdigest()}"
            except (TypeError, ValueError) as e:
                self.logger.warning(f"生成内容哈希失败: {e}")

        # 最后回退到字符串表示
        return f"str:{str(event.raw)}"

    def _update_lru_cache(self, key: str) -> bool:
        """更新LRU缓存

        Args:
            key: 去重键

        Returns:
            True 如果是重复项，False 如果是新项
        """
        if key in self._seen_cache:
            # 命中缓存，移动到末尾（最近使用）
            self._seen_cache.move_to_end(key)
            self._dedup_stats["cache_hits"] += 1
            return True
        else:
            # 未命中，添加到缓存
            self._seen_cache[key] = True
            self._dedup_stats["cache_misses"] += 1

            # 检查缓存大小，必要时移除最久未使用的项
            while len(self._seen_cache) > self.max_size:
                self._seen_cache.popitem(last=False)  # 移除最旧的项

            return False

    def _process_impl(self, events: list[RawEvent]) -> list[RawEvent]:
        """实际的去重处理逻辑"""
        if not events:
            return events

        unique_events: list[RawEvent] = []
        duplicates_count = 0

        for event in events:
            self._dedup_stats["total_input"] += 1

            try:
                dedup_key = self._generate_dedup_key(event)

                # 检查是否重复
                if self._update_lru_cache(dedup_key):
                    duplicates_count += 1
                    self._dedup_stats["duplicates_found"] += 1
                    self.logger.debug(f"发现重复事件: {dedup_key}")
                else:
                    unique_events.append(event)

            except Exception as e:
                # 对于无法生成去重键的事件，保留下来但记录警告
                self.logger.warning(f"生成去重键失败，保留事件: {e}")
                unique_events.append(event)

        if duplicates_count > 0:
            self.logger.info(
                f"去重完成，输入 {len(events)} 个，去除 {duplicates_count} 个重复，输出 {len(unique_events)} 个"
            )

        return unique_events

    def handle_error(self, error: Exception, events: list[RawEvent]) -> list[RawEvent]:
        """去重阶段的错误处理

        对于去重错误，我们选择直接返回原始事件列表，
        这样可以确保数据不丢失（可能会有重复但不会丢数据）。
        """
        self.logger.warning(f"去重处理失败，跳过去重直接返回原始数据: {error}")
        return events

    def get_metrics(self) -> Dict[str, Any]:
        """获取包括去重统计在内的指标"""
        metrics = super().get_metrics()
        metrics.update(self._dedup_stats)
        metrics["cache_size"] = len(self._seen_cache)
        metrics["max_cache_size"] = self.max_size

        # 计算去重率
        if self._dedup_stats["total_input"] > 0:
            metrics["dedup_rate"] = (
                self._dedup_stats["duplicates_found"] / self._dedup_stats["total_input"]
            )
        else:
            metrics["dedup_rate"] = 0.0

        # 计算缓存命中率
        total_cache_access = (
            self._dedup_stats["cache_hits"] + self._dedup_stats["cache_misses"]
        )
        if total_cache_access > 0:
            metrics["cache_hit_rate"] = (
                self._dedup_stats["cache_hits"] / total_cache_access
            )
        else:
            metrics["cache_hit_rate"] = 0.0

        return metrics

    def clear_cache(self):
        """清空去重缓存（用于维护或测试）"""
        self._seen_cache.clear()
        self.logger.info("去重缓存已清空")
