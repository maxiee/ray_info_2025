"""RaySchedulerAdapter: 使用新调度器的适配器实现"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict, List

from ..collectors.base import BaseCollector, CollectorRetryableException, registry as collector_registry
from ..config.settings import get_settings
from ..pipelines import DedupStage, Pipeline, SqlitePersistStage
from ..utils.instance_id import instance_manager
from .state_manager import CollectorStateManager
from .types import JobKind, make_job_id
from . import (
    RayScheduler,
    registry as task_registry,
    Task,
    CollectorTaskConsumer,
)

logger = logging.getLogger("rayinfo.ray_scheduler_adapter")


class RaySchedulerAdapter:
    """基于 RayScheduler 的调度器适配器
    
    使用新的 RayScheduler 替代 APScheduler，提供相同的外部接口
    但内部使用基于 AsyncIO 的时间驱动调度。
    
    主要特性：
    - 保持与现有 SchedulerAdapter 接口兼容
    - 使用 RayScheduler 进行任务调度
    - 支持状态感知的断点续传
    - 自动处理采集器到 TaskConsumer 的转换
    """
    
    def __init__(self):
        """初始化 RayScheduler 适配器"""
        # 创建新的调度器
        self.scheduler = RayScheduler()
        
        # 从配置中获取存储设置
        settings = get_settings()
        
        # 数据处理管道
        self.pipeline = Pipeline([
            DedupStage(max_size=1000),
            SqlitePersistStage(settings.storage.db_path),
        ])
        
        # 状态管理器
        self.state_manager = CollectorStateManager.get_instance(
            settings.storage.db_path
        )
        
        # 已注册的任务消费者映射
        self._consumer_map: Dict[str, CollectorTaskConsumer] = {}
        
        logger.info(f"RayScheduler 适配器初始化完成，数据库路径: {settings.storage.db_path}")
    
    def start(self):
        """启动调度器"""
        # 注意：这里不能直接 await，需要在异步上下文中调用
        # 实际的启动会在 lifespan 中处理
        logger.info("RayScheduler adapter ready to start")
    
    def shutdown(self):
        """关闭调度器"""
        # 注意：这里不能直接 await，需要在异步上下文中调用
        logger.info("RayScheduler adapter shutdown requested")
    
    async def async_start(self):
        """异步启动调度器"""
        await self.scheduler.start()
    
    async def async_shutdown(self):
        """异步关闭调度器"""
        await self.scheduler.stop()
    
    def _register_collector_consumer(
        self,
        collector: BaseCollector,
        param: Optional[str] = None,
    ) -> CollectorTaskConsumer:
        """注册采集器为任务消费者
        
        Args:
            collector: 采集器实例
            param: 参数化采集器的参数
            
        Returns:
            创建的任务消费者
        """
        # 创建任务消费者
        consumer = CollectorTaskConsumer(
            collector=collector,
            pipeline=self.pipeline,
            param=param,
        )
        
        # 注册到任务注册表
        task_registry.register(consumer)
        
        # 记录映射关系
        self._consumer_map[consumer.name] = consumer
        
        logger.debug(
            "注册采集器任务消费者 name=%s collector=%s param=%s",
            consumer.name,
            collector.name,
            param
        )
        
        return consumer
    
    def _create_periodic_task(
        self,
        consumer: CollectorTaskConsumer,
        interval_seconds: int,
    ) -> None:
        """创建周期性任务
        
        Args:
            consumer: 任务消费者
            interval_seconds: 执行间隔（秒）
        """
        async def schedule_next():
            """调度下一次执行"""
            while self.scheduler.is_running():
                # 计算下次执行时间
                next_time = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
                
                # 创建任务
                task = consumer.produce({"schedule_at": next_time})
                
                # 添加到调度器
                self.scheduler.add_task(task)
                
                # 等待间隔时间
                await asyncio.sleep(interval_seconds)
        
        # 启动周期调度协程
        import asyncio
        asyncio.create_task(schedule_next())
    
    def _schedule_initial_task(
        self,
        consumer: CollectorTaskConsumer,
        delay_seconds: float = 0,
    ) -> None:
        """调度初始执行任务
        
        Args:
            consumer: 任务消费者
            delay_seconds: 延迟时间（秒）
        """
        # 计算执行时间
        execute_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        
        # 创建任务
        task = consumer.produce({"schedule_at": execute_at})
        
        # 添加到调度器
        self.scheduler.add_task(task)
        
        logger.debug(
            "调度初始任务 consumer=%s delay=%.1f seconds",
            consumer.name,
            delay_seconds
        )
    
    def add_collector_job_with_state(self, collector: BaseCollector) -> list[str]:
        """添加带状态感知的数据收集器调度任务
        
        集成断点续传功能，根据上次执行时间智能决定初始调度策略。
        
        Args:
            collector: 要添加调度的数据收集器实例
            
        Returns:
            已添加的任务ID列表（为了兼容性）
        """
        job_ids = []
        
        try:
            # 检查是否为参数化采集器
            param_jobs = getattr(collector, "list_param_jobs", lambda: None)()
            
            if param_jobs is not None:
                # 参数化采集器
                for param_key, interval in param_jobs:
                    if interval is None:
                        logger.warning(
                            "参数化采集器任务间隔为空，跳过 collector=%s param=%s",
                            collector.name,
                            param_key,
                        )
                        continue
                    
                    # 注册实例
                    instance_id = instance_manager.register_instance(collector, param_key)
                    
                    # 创建任务消费者
                    consumer = self._register_collector_consumer(collector, param_key)
                    
                    # 计算初始执行时间
                    next_run_time = self.state_manager.calculate_next_run_time(
                        collector_name=collector.name,
                        param_key=param_key,
                        interval_seconds=interval,
                    )
                    
                    # 调度初始任务
                    if self.state_manager.should_run_immediately(
                        collector_name=collector.name,
                        param_key=param_key,
                        interval_seconds=interval,
                    ):
                        delay = max(0, next_run_time - time.time())
                        self._schedule_initial_task(consumer, delay)
                        
                        initial_job_id = make_job_id(collector.name, param_key, JobKind.Initial)
                        job_ids.append(initial_job_id)
                        
                        logger.info(
                            "添加参数化采集器初始任务 collector=%s param=%s delay=%.1f",
                            collector.name,
                            param_key,
                            delay,
                        )
                    
                    # 创建周期性任务调度
                    self._create_periodic_task(consumer, interval)
                    
                    periodic_job_id = make_job_id(collector.name, param_key, JobKind.Periodic)
                    job_ids.append(periodic_job_id)
                    
                    logger.info(
                        "添加参数化采集器周期任务 collector=%s param=%s interval=%d",
                        collector.name,
                        param_key,
                        interval,
                    )
            else:
                # 普通采集器
                interval = collector.default_interval_seconds
                if interval is None:
                    logger.warning(
                        "普通采集器间隔为空，使用默认值60秒 collector=%s",
                        collector.name,
                    )
                    interval = 60
                
                # 注册实例
                instance_id = instance_manager.register_instance(collector, None)
                
                # 创建任务消费者
                consumer = self._register_collector_consumer(collector, None)
                
                # 计算初始执行时间
                next_run_time = self.state_manager.calculate_next_run_time(
                    collector_name=collector.name,
                    param_key=None,
                    interval_seconds=interval,
                )
                
                # 调度初始任务
                if self.state_manager.should_run_immediately(
                    collector_name=collector.name,
                    param_key=None,
                    interval_seconds=interval,
                ):
                    delay = max(0, next_run_time - time.time())
                    self._schedule_initial_task(consumer, delay)
                    
                    initial_job_id = make_job_id(collector.name, None, JobKind.Initial)
                    job_ids.append(initial_job_id)
                    
                    logger.info(
                        "添加普通采集器初始任务 collector=%s delay=%.1f",
                        collector.name,
                        delay,
                    )
                
                # 创建周期性任务调度
                self._create_periodic_task(consumer, interval)
                
                periodic_job_id = make_job_id(collector.name, None, JobKind.Periodic)
                job_ids.append(periodic_job_id)
                
                logger.info(
                    "添加普通采集器周期任务 collector=%s interval=%d",
                    collector.name,
                    interval,
                )
            
            logger.info(
                "状态感知调度完成 collector=%s 添加任务数=%d",
                collector.name,
                len(job_ids),
            )
            
            return job_ids
            
        except Exception as e:
            logger.error(
                "添加状态感知采集器任务失败 collector=%s error=%s",
                collector.name,
                e
            )
            return []
    
    def add_collector_job(self, collector: BaseCollector) -> list[str]:
        """添加数据收集器的调度任务（兼容接口）
        
        Args:
            collector: 要添加调度的数据收集器实例
            
        Returns:
            已添加的任务ID列表
        """
        return self.add_collector_job_with_state(collector)
    
    async def run_instance_by_id(self, instance_id: str) -> Dict[str, str]:
        """根据实例ID手动触发采集器实例（兼容接口）
        
        Args:
            instance_id: 采集器实例的唯一ID
            
        Returns:
            执行结果字典
        """
        # 获取实例信息
        instance = instance_manager.get_instance(instance_id)
        if instance is None:
            raise ValueError(f"Instance not found: {instance_id}")
        
        try:
            # 构造消费者名称
            consumer_name = instance.collector.name
            if instance.param is not None:
                consumer_name = f"{instance.collector.name}:{instance.param}"
            
            # 查找对应的任务消费者
            consumer = self._consumer_map.get(consumer_name)
            if consumer is None:
                # 动态创建消费者
                consumer = self._register_collector_consumer(
                    instance.collector,
                    instance.param
                )
            
            # 创建立即执行的任务
            task = consumer.produce({"schedule_at": datetime.now(timezone.utc)})
            
            # 直接执行任务
            await consumer.consume(task)
            
            logger.info(
                "[manual] 手动触发实例成功 instance_id=%s consumer=%s",
                instance_id,
                consumer_name,
            )
            
            return {
                "status": "success",
                "message": f"Successfully triggered instance {instance_id}",
            }
            
        except Exception as e:
            logger.error(
                "[manual] 手动触发实例失败 instance_id=%s error=%s",
                instance_id,
                str(e)
            )
            return {
                "status": "error",
                "message": f"Failed to trigger instance {instance_id}: {str(e)}",
            }
    
    def load_all_collectors(self):
        """加载并添加所有已注册的收集器任务（兼容接口）"""
        for collector in collector_registry.all():
            self.add_collector_job_with_state(collector)
    
    # 兼容性方法
    async def run_collector_with_state_update(
        self, collector: BaseCollector, param: Optional[str] = None
    ) -> None:
        """执行单次数据收集任务并更新状态（兼容接口）
        
        这个方法主要用于保持向后兼容性。
        """
        # 构造消费者名称
        consumer_name = collector.name
        if param is not None:
            consumer_name = f"{collector.name}:{param}"
        
        # 查找或创建任务消费者
        consumer = self._consumer_map.get(consumer_name)
        if consumer is None:
            consumer = self._register_collector_consumer(collector, param)
        
        # 创建任务并执行
        task = consumer.produce({"param": param} if param else {})
        
        try:
            await consumer.consume(task)
            
            # 更新状态
            self.state_manager.update_execution_time(
                collector_name=collector.name,
                param_key=param,
                timestamp=time.time(),
            )
            
        except CollectorRetryableException as e:
            # 处理可重试异常
            logger.warning(
                "[run] 采集器执行失败，需要重试 collector=%s param=%s reason=%s",
                collector.name,
                param,
                e.retry_reason,
            )
            
            # 计算重试延迟
            default_retry_delay = 3600  # 默认1小时
            retry_delay = e.retry_after if e.retry_after is not None else default_retry_delay
            retry_delay = max(60, retry_delay)  # 最小60秒
            
            # 创建重试任务
            retry_time = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
            retry_task = consumer.produce({"schedule_at": retry_time})
            
            # 添加到调度器
            self.scheduler.add_task(retry_task)
            
            logger.info(
                "[run] 已安排重试任务 reason=%s retry_in=%.1f小时",
                e.retry_reason,
                retry_delay / 3600,
            )