from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, List, Dict, Any, Optional

from ..base import ParameterizedCollector, RawEvent
from ...config.settings import get_settings

logger = logging.getLogger("rayinfo.collector.mes")


class MesCollector(ParameterizedCollector):
    """使用外部 `mes` CLI 进行多搜索引擎查询的采集器.

    当前实现：
    - 固定关键词列表（示例）与固定搜索引擎 (duckduckgo)
    - 运行: mes search <query> --output json --limit N
    - 支持新的 JSON 格式: {"results": [...], "count": N, "rate_limit": {...}}
    - 兼容旧的 JSON 格式: [result1, result2, ...]
    - 将每条结果转换为 RawEvent (post_id 使用结果 url 便于去重)
    - 记录 API 使用配额信息

    未来扩展预留：
    - _choose_engine(): 支持 Google API 配额内优先使用, 超限降级到其它引擎
    - 外部配置驱动: 关键词列表、limit、时间窗口、引擎策略
    - 参数化任务: 通过 list_param_jobs() 提供不同 query 参数
    """

    name = "mes.search"

    def __init__(self):
        super().__init__()
        self._loaded = False
        self._query_jobs: list[tuple[str, int, str, Optional[str]]] = (
            []
        )  # (query, interval, engine, time_range)

    @property
    def default_interval_seconds(self) -> int | None:
        return 300

    def _ensure_loaded(self):
        if self._loaded:
            return
        settings = get_settings()
        # 新结构：settings.search_engine 是列表 (query, interval_seconds, engine, time_range)
        if settings.search_engine:
            self._query_jobs = [
                (item.query, item.interval_seconds, item.engine, item.time_range)
                for item in settings.search_engine
            ]
        else:
            self._query_jobs = []
        self._loaded = True

    def list_param_jobs(self) -> list[tuple[str, int]]:
        """供调度器调用：返回 (query, interval_seconds).

        调度器将为每个 query 创建独立 job，并在运行时传入 param=query。
        """
        self._ensure_loaded()
        return [(q, interval) for q, interval, _engine, _time_range in self._query_jobs]

    async def setup(self) -> None:  # 可选初始化, 这里暂无
        return None

    def _choose_engine(self, query: str) -> str:
        """预留搜索引擎选择策略.

        当前直接返回 "duckduckgo". 未来可：
        1. 若 Google API 配额剩余 -> 返回 google
        2. 否则 fallback 到 duckduckgo / bing / searx
        """
        return "duckduckgo"

    async def _run_mes(
        self, query: str, engine: str, time_range: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """调用 mes CLI 并解析 JSON 输出.

        支持新的 JSON 格式: {"results": [...], "count": N, "rate_limit": {...}}
        兼容旧的 JSON 格式: [result1, result2, ...]
        会记录 API 使用配额信息以供监控。

        失败处理策略：
        - 非 0 退出码: 记录日志并返回空列表
        - JSON 解析失败: 记录日志返回空列表
        """
        # 组装命令
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
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning(
                "mes command failed rc=%s engine=%s query=%s stderr=%s",
                proc.returncode,
                engine,
                query,
                stderr.decode(errors="ignore"),
            )
            return []
        try:
            data = json.loads(stdout.decode())
            # 适配新的 JSON 格式：{"results": [...], "count": N, "rate_limit": {...}}
            if isinstance(data, dict) and "results" in data:
                results = data["results"]
                if not isinstance(results, list):
                    logger.warning("unexpected mes results type: %s", type(results))
                    return []
                # 记录 rate_limit 信息（如果存在）
                if "rate_limit" in data:
                    rate_limit = data["rate_limit"]
                    logger.info(
                        "Search API rate limit info - used: %s/%s, remaining: %s, limit_exceeded: %s",
                        rate_limit.get("requests_used", "unknown"),
                        rate_limit.get("daily_limit", "unknown"),
                        rate_limit.get("requests_remaining", "unknown"),
                        rate_limit.get("limit_exceeded", "unknown"),
                    )
                return results
            # 兼容旧格式（直接是数组）
            elif isinstance(data, list):
                logger.info("Using legacy mes output format (direct array)")
                return data
            else:
                logger.warning("unexpected mes output format: %s", type(data))
                return []
        except json.JSONDecodeError as e:  # pragma: no cover - 解析异常日志
            logger.error("parse mes json failed query=%s error=%s", query, e)
            return []

    async def fetch(self, param=None) -> AsyncIterator[RawEvent]:  # noqa: D401
        """执行搜索任务并返回结果事件。

        作为参数化采集器，此方法必须接收具体的查询参数(param)。
        调度器会为每个配置的查询创建独立任务，并传入对应的查询关键词。

        Args:
            param: 查询关键词字符串，由调度器传入。对于参数化采集器，不应为None。

        Yields:
            RawEvent: 包含搜索结果的原始事件
        """
        self._ensure_loaded()

        if param is None:
            # 对于参数化采集器，param 不应为 None
            # 这通常表示调度器配置错误或直接调用了 fetch() 而没有参数
            logger.warning(
                "MesCollector.fetch() called without param, this should not happen in normal operation. "
                "Parameterized collectors require specific query parameters."
            )
            return

        # 只处理传入的特定查询参数
        query = param

        # 构建 per-query engine/time_range map
        engine_map = {q: eng for q, _i, eng, _tr in self._query_jobs}
        time_range_map = {q: tr for q, _i, _eng, tr in self._query_jobs}

        # 获取该查询的配置
        engine = engine_map.get(query) or self._choose_engine(query)
        time_range = time_range_map.get(query)

        logger.info(
            "执行搜索任务: query=%s, engine=%s, time_range=%s",
            query,
            engine,
            time_range,
        )

        # 执行搜索
        results = await self._run_mes(query, engine, time_range)

        for item in results:
            # 结果字段: title, url, description, engine
            url = item.get("url") or ""
            # post_id 用 url 作为去重键 (若缺失则 hash 整个对象)
            raw: Dict[str, Any] = {
                "post_id": url or json.dumps(item, ensure_ascii=False),
                "query": query,
                "title": item.get("title"),
                "url": url,
                "description": item.get("description"),
                "engine": item.get("engine"),
            }
            yield RawEvent(source=self.name, raw=raw)
