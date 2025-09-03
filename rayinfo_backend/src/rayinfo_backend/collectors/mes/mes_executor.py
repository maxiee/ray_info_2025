"""MES 命令执行器 - 提供带同步锁的协程安全执行机制

这个模块实现了对 mes CLI 命令的协程安全调用，确保同一时间只有一个 mes 命令在执行。
这对于避免搜索引擎 API 的并发调用限制和提高系统稳定性是非常重要的。

主要特性：
- 使用 asyncio.Lock 确保 mes 命令的串行执行
- 保持原有的 JSON 解析和错误处理逻辑
- 支持配额检测和异常处理
- 线程安全的单例模式设计
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

from ..base import QuotaExceededException

logger = logging.getLogger("rayinfo.collector.mes.executor")


class MesExecutor:
    """MES 命令执行器 - 提供协程安全的 mes 命令调用

    这个类实现了单例模式，确保整个应用中只有一个 MesExecutor 实例。
    使用 asyncio.Lock 来保证同一时间只有一个 mes 命令在执行。
    """

    _instance: Optional["MesExecutor"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "MesExecutor":
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._mes_lock = asyncio.Lock()
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化执行器"""
        if not self._initialized:
            self._mes_lock = asyncio.Lock()
            self._initialized = True
            logger.info("MesExecutor 初始化完成")

    async def execute_mes_command(
        self, query: str, engine: str, time_range: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """执行 mes 命令并解析结果

        这个方法使用 asyncio.Lock 确保同一时间只有一个 mes 命令在执行。
        其他并发调用将等待当前命令完成。

        Args:
            query: 搜索查询关键词
            engine: 搜索引擎名称 (google, duckduckgo, bing 等)
            time_range: 时间范围过滤器 (可选)

        Returns:
            List[Dict[str, Any]]: 搜索结果列表

        Raises:
            QuotaExceededException: 当 API 配额超限时抛出
        """
        async with self._mes_lock:
            logger.info(
                "开始执行 mes 命令 (已获得锁): query=%s, engine=%s, time_range=%s",
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
            finally:
                logger.debug("释放 mes 命令执行锁")

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
            QuotaExceededException: 当检测到 Google API 配额超限时
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
            QuotaExceededException: 当检测到 Google API 配额超限时
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
            QuotaExceededException: 当检测到 Google API 配额超限时
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
            raise QuotaExceededException(
                api_type="google",
                reset_time=reset_time,
                message=f"Google Search API 每日配额已超限 (已使用 {requests_used}/{daily_limit})",
            )


# 创建全局单例实例
_mes_executor = MesExecutor()


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
        QuotaExceededException: 当 API 配额超限时抛出
    """
    return await _mes_executor.execute_mes_command(query, engine, time_range)
