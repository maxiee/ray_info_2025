from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, Any, Set
from abc import ABC, abstractmethod
from collections import OrderedDict
import time
import hashlib
import json

from ..collectors.base import RawEvent
from ..models.info_item import RawInfoItem, DatabaseManager


class PipelineStage(ABC):
    """管道处理阶段抽象基类
    
    提供统一的错误处理、指标收集和生命周期管理。
    所有管道阶段都应继承此类并实现具体的处理逻辑。
    """
    
    def __init__(self, stage_name: str | None = None):
        """初始化管道阶段
        
        Args:
            stage_name: 阶段名称，用于日志和指标标识
        """
        self.stage_name = stage_name or self.__class__.__name__
        self.logger = logging.getLogger(f"rayinfo.pipeline.{self.stage_name.lower()}")
        
        # 指标统计
        self._metrics = {
            "processed_count": 0,
            "error_count": 0,
            "total_processing_time": 0.0,
            "last_processed_at": None,
            "last_error_at": None,
        }
    
    @abstractmethod
    def _process_impl(self, events: list[RawEvent]) -> list[RawEvent]:
        """实际的处理逻辑实现
        
        子类必须实现此方法来定义具体的处理逻辑。
        
        Args:
            events: 要处理的事件列表
            
        Returns:
            处理后的事件列表
        """
        raise NotImplementedError
    
    def process(self, events: list[RawEvent]) -> list[RawEvent]:
        """处理事件列表的统一入口
        
        提供统一的错误处理、指标收集和日志记录。
        
        Args:
            events: 要处理的事件列表
            
        Returns:
            处理后的事件列表
        """
        if not events:
            return events
        
        start_time = time.time()
        
        try:
            self.logger.debug(f"开始处理 {len(events)} 个事件")
            
            # 调用子类实现
            result = self._process_impl(events)
            
            # 更新指标
            processing_time = time.time() - start_time
            self._metrics["processed_count"] += len(events)
            self._metrics["total_processing_time"] += processing_time
            self._metrics["last_processed_at"] = datetime.utcnow()
            
            self.logger.debug(
                f"处理完成，输入 {len(events)} 个，输出 {len(result)} 个，耗时 {processing_time:.3f}s"
            )
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self._metrics["error_count"] += 1
            self._metrics["last_error_at"] = datetime.utcnow()
            
            self.logger.error(
                f"处理阶段失败: {e}，处理事件数: {len(events)}，耗时: {processing_time:.3f}s"
            )
            
            # 尝试错误恢复
            return self.handle_error(e, events)
    
    def handle_error(self, error: Exception, events: list[RawEvent]) -> list[RawEvent]:
        """错误处理机制
        
        子类可以重写此方法来实现自定义的错误处理逻辑。
        默认实现返回空列表，防止错误传播。
        
        Args:
            error: 发生的异常
            events: 导致错误的事件列表
            
        Returns:
            错误恢复后的事件列表（默认为空）
        """
        self.logger.warning(f"使用默认错误处理，丢弃 {len(events)} 个事件")
        return []
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取处理指标
        
        Returns:
            包含各种指标的字典
        """
        metrics = self._metrics.copy()
        metrics["stage_name"] = self.stage_name
        
        # 计算平均处理时间
        if metrics["processed_count"] > 0:
            metrics["avg_processing_time"] = (
                metrics["total_processing_time"] / metrics["processed_count"]
            )
        else:
            metrics["avg_processing_time"] = 0.0
        
        return metrics
    
    def reset_metrics(self):
        """重置指标统计"""
        self._metrics = {
            "processed_count": 0,
            "error_count": 0,
            "total_processing_time": 0.0,
            "last_processed_at": None,
            "last_error_at": None,
        }


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
                hash_obj = hashlib.md5(content_str.encode('utf-8'))
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
        self.logger.warning(
            f"去重处理失败，跳过去重直接返回原始数据: {error}"
        )
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
        total_cache_access = self._dedup_stats["cache_hits"] + self._dedup_stats["cache_misses"]
        if total_cache_access > 0:
            metrics["cache_hit_rate"] = self._dedup_stats["cache_hits"] / total_cache_access
        else:
            metrics["cache_hit_rate"] = 0.0
        
        return metrics
    
    def clear_cache(self):
        """清空去重缓存（用于维护或测试）"""
        self._seen_cache.clear()
        self.logger.info("去重缓存已清空")


class PersistStage(PipelineStage):
    """占位持久化阶段

    仅用于测试和演示，将数据打印到控制台。
    生产环境请使用 SqlitePersistStage。
    """
    
    def __init__(self):
        super().__init__("PersistStage")
    
    def _process_impl(self, events: list[RawEvent]) -> list[RawEvent]:
        """占位实现，仅打印日志"""
        for e in events:
            print(f"[Persist] {e.source} {e.raw}")
        return events


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
            post_id=raw_data.get("post_id") or DataTransformer._generate_fallback_id(raw_data),
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
        import hashlib
        import json
        
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


class SqlitePersistStage(PipelineStage):
    """重构后的 SQLite 持久化阶段

    职责单一：仅负责数据的持久化存储。
    数据转换和验证逻辑已分离到独立的类中。
    支持批量写入、幂等性和完善的错误处理。
    """
    
    def __init__(self, db_path: str = "rayinfo.db", batch_size: int = 100):
        """初始化 SQLite 持久化阶段

        Args:
            db_path: SQLite 数据库文件路径
            batch_size: 批量处理大小
        """
        super().__init__("SqlitePersistStage")
        self.db_path = db_path
        self.batch_size = batch_size
        self.db_manager = DatabaseManager(db_path)
        
        # 持久化统计
        self._persist_stats = {
            "saved_count": 0,
            "failed_count": 0,
            "debug_skipped_count": 0,
            "validation_failed_count": 0,
        }
        
        self.logger.info(f"SQLite 持久化阶段初始化完成，数据库路径: {db_path}")
    
    def _process_impl(self, events: list[RawEvent]) -> list[RawEvent]:
        """实际的持久化处理逻辑"""
        if not events:
            return events
        
        # 过滤和验证事件
        valid_events = self._filter_and_validate_events(events)
        
        if not valid_events:
            return events
        
        # 批量保存
        self._batch_save_events(valid_events)
        
        return events
    
    def _filter_and_validate_events(self, events: list[RawEvent]) -> list[RawEvent]:
        """过滤和验证事件列表"""
        valid_events = []
        
        for event in events:
            # 过滤 debug 事件
            if event.debug:
                self._persist_stats["debug_skipped_count"] += 1
                continue
            
            # 验证事件
            is_valid, error_msg = EventValidator.validate_event(event)
            if not is_valid:
                self._persist_stats["validation_failed_count"] += 1
                self.logger.warning(f"事件验证失败: {error_msg}, 数据: {event.raw}")
                continue
            
            valid_events.append(event)
        
        return valid_events
    
    def _batch_save_events(self, events: list[RawEvent]):
        """批量保存事件列表"""
        session = self.db_manager.get_session()
        
        try:
            # 按批次处理
            for i in range(0, len(events), self.batch_size):
                batch = events[i:i + self.batch_size]
                self._save_batch(session, batch)
            
            # 提交事务
            session.commit()
            
            self.logger.info(f"成功保存 {len(events)} 条记录到数据库")
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"批量保存失败，已回滚: {e}")
            raise
        finally:
            session.close()
    
    def _save_batch(self, session, batch: list[RawEvent]):
        """保存单个批次的事件"""
        for event in batch:
            try:
                # 转换为数据库实体
                item = DataTransformer.transform_event_to_item(event)
                
                # 使用 merge 实现 UPSERT 操作，确保幂等性
                session.merge(item)
                self._persist_stats["saved_count"] += 1
                
            except Exception as e:
                self._persist_stats["failed_count"] += 1
                self.logger.error(f"保存单条记录失败: {e}, 数据: {event.raw}")
                # 继续处理其他记录，不中断整个批次
    
    def handle_error(self, error: Exception, events: list[RawEvent]) -> list[RawEvent]:
        """持久化阶段的错误处理
        
        对于持久化错误，我们选择记录错误但不阻断后续处理。
        """
        self.logger.error(f"持久化处理失败，不影响后续处理: {error}")
        return events
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取包括持久化统计在内的指标"""
        metrics = super().get_metrics()
        metrics.update(self._persist_stats)
        metrics["db_path"] = self.db_path
        metrics["batch_size"] = self.batch_size
        return metrics

class Pipeline:
    def __init__(self, stages: list[PipelineStage]):
        self.stages = stages

    def run(self, events: list[RawEvent]) -> list[RawEvent]:
        data = events
        for st in self.stages:
            data = st.process(data)
        return data
