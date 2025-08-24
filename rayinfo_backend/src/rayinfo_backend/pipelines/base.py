from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from ..collectors.base import RawEvent
from ..models.info_item import RawInfoItem, DatabaseManager


class PipelineStage:
    def process(self, events: list[RawEvent]) -> list[RawEvent]:  # noqa: D401
        return events


class DedupStage(PipelineStage):
    def __init__(self, max_size: int = 1000):
        self._seen: list[str] = []
        self._max_size = max_size

    def process(self, events: list[RawEvent]) -> list[RawEvent]:
        out: list[RawEvent] = []
        for e in events:
            key = e.raw.get("post_id") or str(e.raw)
            if key in self._seen:
                continue
            self._seen.append(key)
            if len(self._seen) > self._max_size:
                self._seen = self._seen[-self._max_size :]
            out.append(e)
        return out


class PersistStage(PipelineStage):
    """占位持久化阶段

    仅用于测试和演示，将数据打印到控制台。
    生产环境请使用 SqlitePersistStage。
    """

    def process(self, events: list[RawEvent]) -> list[RawEvent]:
        for e in events:
            print(f"[Persist] {e.source} {e.raw}")
        return events


class SqlitePersistStage(PipelineStage):
    """SQLite 持久化阶段

    将采集到的原始数据保存到 SQLite 数据库中，支持批量写入和幂等性。
    使用 UPSERT 操作确保相同 post_id 的数据不会重复插入。
    """

    def __init__(self, db_path: str = "rayinfo.db"):
        """初始化 SQLite 持久化阶段

        Args:
            db_path: SQLite 数据库文件路径
        """
        self.logger = logging.getLogger("rayinfo.pipeline.persist")
        self.db_manager = DatabaseManager(db_path)
        self.logger.info(f"SQLite 持久化阶段初始化完成，数据库路径: {db_path}")

    def process(self, events: list[RawEvent]) -> list[RawEvent]:
        """批量保存数据到 SQLite 数据库

        Args:
            events: 要保存的原始事件列表

        Returns:
            原始事件列表（支持链式处理）

        Raises:
            Exception: 数据库操作失败时抛出异常
        """
        if not events:
            return events

        # 过滤掉 debug=True 的事件，不进行持久化
        events_to_persist = [event for event in events if not event.debug]
        
        # 如果没有需要持久化的事件，直接返回
        if not events_to_persist:
            debug_count = len(events) - len(events_to_persist)
            if debug_count > 0:
                self.logger.info(f"跳过了 {debug_count} 个 debug 事件，不进行持久化")
            return events

        session = self.db_manager.get_session()
        saved_count = 0
        error_count = 0
        debug_count = len(events) - len(events_to_persist)

        try:
            for event in events_to_persist:
                try:
                    raw_data = event.raw

                    # 构建数据库记录
                    item = RawInfoItem(
                        post_id=raw_data.get("post_id")
                        or self._generate_fallback_id(raw_data),
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

                    # 使用 merge 实现 UPSERT 操作，确保幂等性
                    session.merge(item)
                    saved_count += 1

                except Exception as e:
                    error_count += 1
                    self.logger.error(f"保存单条记录失败: {e}, 数据: {event.raw}")

            # 提交事务
            session.commit()

            if saved_count > 0:
                self.logger.info(f"成功保存 {saved_count} 条记录到数据库")
            if error_count > 0:
                self.logger.warning(f"保存过程中有 {error_count} 条记录失败")
            if debug_count > 0:
                self.logger.info(f"跳过了 {debug_count} 个 debug 事件，不进行持久化")

        except Exception as e:
            session.rollback()
            self.logger.error(f"数据库事务失败，已回滚: {e}")
            raise
        finally:
            session.close()

        return events

    def _generate_fallback_id(self, raw_data: dict) -> str:
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


class Pipeline:
    def __init__(self, stages: list[PipelineStage]):
        self.stages = stages

    def run(self, events: list[RawEvent]) -> list[RawEvent]:
        data = events
        for st in self.stages:
            data = st.process(data)
        return data
