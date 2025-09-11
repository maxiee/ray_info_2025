"""Task: 调度器调度的最小单元"""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class Task:
    """任务类 - 调度器调度的最小单元
    
    所有 TaskConsumer 共用同一个 Task 类型。每个 Task 在创建时具备唯一 uuid，
    包含执行参数、源信息和调度时间。
    
    Attributes:
        uuid: 每个 Task 的唯一标识符
        args: 传入 Task 的参数，用于 TaskConsumer 消费时使用
        source: Task 创建时对应的 TaskConsumer 的 name
        schedule_at: Task 的调度时间戳，默认为当前时间
    """
    
    def __init__(
        self,
        source: str,
        args: Optional[Dict[str, Any]] = None,
        schedule_at: Optional[datetime] = None,
        uuid: Optional[str] = None,
    ):
        """初始化 Task
        
        Args:
            source: TaskConsumer 的名称
            args: 传入的参数字典，默认为空字典
            schedule_at: 调度时间，默认为当前 UTC 时间
            uuid: 任务唯一标识，默认自动生成
        """
        self.uuid = uuid or str(uuid_lib.uuid4())
        self.args = args or {}
        self.source = source
        self.schedule_at = schedule_at or datetime.now(timezone.utc)
        
        # 确保 schedule_at 是时区感知的
        if self.schedule_at.tzinfo is None:
            # 如果没有时区信息，假设为 UTC
            self.schedule_at = self.schedule_at.replace(tzinfo=timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """将 Task 转换为字典，用于持久化或日志打印
        
        Returns:
            包含 uuid、args、source、schedule_at 的字典
        """
        return {
            "uuid": self.uuid,
            "args": self.args,
            "source": self.source,
            "schedule_at": self.schedule_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        """从字典恢复 Task 实例
        
        Args:
            data: 包含任务信息的字典
            
        Returns:
            恢复的 Task 实例
        """
        schedule_at = datetime.fromisoformat(data["schedule_at"])
        # 确保时区感知
        if schedule_at.tzinfo is None:
            schedule_at = schedule_at.replace(tzinfo=timezone.utc)
            
        return cls(
            uuid=data["uuid"],
            args=data["args"],
            source=data["source"],
            schedule_at=schedule_at,
        )
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"Task(uuid={self.uuid[:8]}, source={self.source}, schedule_at={self.schedule_at})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (
            f"Task(uuid='{self.uuid}', source='{self.source}', "
            f"args={self.args}, schedule_at={self.schedule_at})"
        )