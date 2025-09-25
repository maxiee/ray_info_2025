"""MES 命令执行器

调度器串行运行任务，因此这里不再需要额外的锁控制，
尽量保持实现简单直接。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

from ...ray_scheduler.consumer import BaseTaskConsumer
from ...ray_scheduler.task import Task
from ..base import CollectorRetryableException

logger = logging.getLogger("rayinfo.collector.mes.executor")


class MesExecutor(BaseTaskConsumer):
    """MES 命令执行器，负责通过 CLI 执行搜索任务"""

    def __init__(self, name: str = "mes.search"):
        super().__init__(name)
        logger.info(
            "MesExecutor 初始化完成: name=%s",
            name,
        )

    async def consume(self, task: Task) -> None:
        """消费一个 MES 搜索任务

        从 Task.args 中提取搜索参数并执行 mes 命令。
        预期的 args 格式：
        {
            "query": str,          # 搜索查询关键词
            "engine": str,         # 搜索引擎名称 (google, duckduckgo, bing 等)
            "time_range": str,     # 时间范围过滤器 (可选)
        }

        Args:
            task: 要消费的任务

        Raises:
            ValueError: 当任务参数格式不正确时
            CollectorRetryableException: 当 API 配额超限时抛出
        """
        logger.info("开始消费 MES 任务: %s", task)

        # 验证任务来源
        if task.source != self.name:
            logger.warning("任务来源不匹配: 预期=%s, 实际=%s", self.name, task.source)

        # 提取任务参数
        args = task.args
        query = args.get("query")
        engine = args.get("engine")
        time_range = args.get("time_range")

        # 验证必需参数
        if not query:
            raise ValueError("Missing required parameter: query")
        if not engine:
            raise ValueError("Missing required parameter: engine")

        logger.info(
            "执行 MES 搜索任务: uuid=%s, query=%s, engine=%s, time_range=%s",
            task.uuid,
            query,
            engine,
            time_range,
        )

        try:
            # 执行搜索
            results = await self.execute_mes_command(query, engine, time_range)
            logger.info(
                "MES 任务完成: uuid=%s, 结果数量=%d",
                task.uuid,
                len(results),
            )

            # 这里可以根据需要处理搜索结果
            # 例如：保存到数据库、发送通知等

        except Exception as e:
            logger.error(
                "MES 任务执行失败: uuid=%s, error=%s",
                task.uuid,
                str(e),
            )
            raise

    async def execute_mes_command(
        self, query: str, engine: str, time_range: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """执行 mes 命令并解析结果

        Args:
            query: 搜索查询关键词
            engine: 搜索引擎名称 (google, duckduckgo, bing 等)
            time_range: 时间范围过滤器 (可选)

        Returns:
            List[Dict[str, Any]]: 搜索结果列表

        Raises:
            CollectorRetryableException: 当 API 配额超限时抛出
        """
        logger.info(
            "开始执行 mes 命令: query=%s, engine=%s, time_range=%s",
            query,
            engine,
            time_range,
        )

        try:
            result = await self._run_mes_internal(query, engine, time_range)
            logger.info(
                "mes 命令执行完成: query=%s, engine=%s, 结果数量=%d",
                query,
                engine,
                len(result),
            )
            return result
        except Exception as e:
            logger.error(
                "mes 命令执行失败: query=%s, engine=%s, error=%s",
                query,
                engine,
                str(e),
            )
            raise

    async def _run_mes_internal(
        self, query: str, engine: str, time_range: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """内部方法：实际执行 mes CLI 命令

        这个方法包含了原始的 mes 命令调用逻辑，包括：
        - 构建命令参数
        - 执行子进程
        - 解析 JSON 输出
        - 处理新旧格式兼容
        - 配额检测和异常处理

        Args:
            query: 搜索查询关键词
            engine: 搜索引擎名称
            time_range: 时间范围过滤器 (可选)

        Returns:
            List[Dict[str, Any]]: 解析后的搜索结果列表

        Raises:
            CollectorRetryableException: 当检测到 Google API 配额超限时
        """
        # 组装命令参数
        cmd = [
            "mes",
            "search",
            query,
            "--engine",
            engine,
            "--output",
            "json",
        ]

        # 添加时间范围参数（如果指定）
        if time_range:
            cmd.extend(["--time", time_range])

        logger.debug("执行命令: %s", " ".join(cmd))

        # 创建子进程执行 mes 命令
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        # 检查命令执行是否成功
        if proc.returncode != 0:
            logger.warning(
                "mes 命令执行失败: rc=%s, engine=%s, query=%s, stderr=%s",
                proc.returncode,
                engine,
                query,
                stderr.decode(errors="ignore"),
            )
            return []

        # 解析 JSON 输出
        try:
            data = json.loads(stdout.decode())
            return self._parse_mes_output(data, engine)
        except json.JSONDecodeError as e:
            logger.error("mes JSON 解析失败: query=%s, error=%s", query, e)
            return []

    def _parse_mes_output(
        self, data: Union[Dict[str, Any], List[Dict[str, Any]]], engine: str
    ) -> List[Dict[str, Any]]:
        """解析 mes 命令的 JSON 输出

        支持两种格式：
        1. 新格式: {"results": [...], "count": N, "rate_limit": {...}}
        2. 旧格式: [result1, result2, ...]

        Args:
            data: 解析后的 JSON 数据
            engine: 搜索引擎名称，用于配额检测

        Returns:
            List[Dict[str, Any]]: 搜索结果列表

        Raises:
            CollectorRetryableException: 当检测到 Google API 配额超限时
        """
        # 处理新的 JSON 格式: {"results": [...], "count": N, "rate_limit": {...}}
        if isinstance(data, dict) and "results" in data:
            results = data["results"]

            if not isinstance(results, list):
                logger.warning("意外的 mes 结果类型: %s", type(results))
                return []

            # 处理 rate_limit 信息（如果存在）
            if "rate_limit" in data:
                self._handle_rate_limit_info(data["rate_limit"], engine)

            return results

        # 兼容旧格式（直接是数组）
        elif isinstance(data, list):
            logger.info("使用旧版 mes 输出格式（直接数组）")
            return data

        else:
            logger.warning("意外的 mes 输出格式: %s", type(data))
            return []

    def _handle_rate_limit_info(self, rate_limit: Dict[str, Any], engine: str) -> None:
        """处理 API 速率限制信息

        Args:
            rate_limit: 速率限制信息字典
            engine: 搜索引擎名称

        Raises:
            CollectorRetryableException: 当检测到 Google API 配额超限时
        """
        limit_exceeded = rate_limit.get("limit_exceeded", False)
        requests_used = rate_limit.get("requests_used", 0)
        daily_limit = rate_limit.get("daily_limit", 0)
        requests_remaining = rate_limit.get("requests_remaining", 0)

        logger.info(
            "搜索 API 速率限制信息 - 已使用: %s/%s, 剩余: %s, 超限: %s",
            requests_used,
            daily_limit,
            requests_remaining,
            limit_exceeded,
        )

        # 检查是否达到 Google API 限额
        if limit_exceeded and engine.lower() == "google":
            # 计算下一次重置时间（24小时后）
            reset_time = time.time() + 24 * 3600  # 24小时后

            logger.warning(
                "Google API 每日配额已超限 - 已使用: %s/%s, 引擎: %s",
                requests_used,
                daily_limit,
                engine,
            )

            # 抛出配额超限异常，调度器会处理重调度逻辑
            reset_delay = reset_time - time.time() if reset_time else None
            raise CollectorRetryableException(
                retry_reason="google_api_quota",
                retry_after=reset_delay,
                message=f"Google Search API 每日配额已超限 (已使用 {requests_used}/{daily_limit})",
            )


# 创建全局单例实例
_mes_executor = MesExecutor()


def get_mes_executor() -> MesExecutor:
    """获取 MES 执行器单例实例

    Returns:
        MesExecutor: 全局单例实例
    """
    return _mes_executor


async def execute_mes_command(
    query: str, engine: str, time_range: Optional[str] = None
) -> List[Dict[str, Any]]:
    """便利函数：执行 mes 命令

    这是一个模块级别的便利函数，内部使用全局的 MesExecutor 单例。

    Args:
        query: 搜索查询关键词
        engine: 搜索引擎名称
        time_range: 时间范围过滤器 (可选)

    Returns:
        List[Dict[str, Any]]: 搜索结果列表

    Raises:
        CollectorRetryableException: 当 API 配额超限时抛出
    """
    return await _mes_executor.execute_mes_command(query, engine, time_range)
