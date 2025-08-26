"""持久化处理阶段模块

本模块包含数据持久化相关的管道阶段实现。
"""

from __future__ import annotations

from typing import Any, Dict

from ..collectors.base import RawEvent
from ..models.info_item import DatabaseManager
from .stage_base import PipelineStage
from .utils import DataTransformer, EventValidator


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
        # 使用单例的 DatabaseManager
        self.db_manager = DatabaseManager.get_instance(db_path)

        # 持久化统计
        self._persist_stats = {
            "saved_count": 0,
            "failed_count": 0,
            "debug_skipped_count": 0,
            "validation_failed_count": 0,
        }

        self.logger.info(
            f"SQLite 持久化阶段初始化完成，数据库路径: {db_path}（使用单例模式）"
        )

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
                batch = events[i : i + self.batch_size]
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
