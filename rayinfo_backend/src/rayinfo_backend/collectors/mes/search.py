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
    - 将每条结果转换为 RawEvent (post_id 使用结果 url 便于去重)

    未来扩展预留：
    - _choose_engine(): 支持 Google API 配额内优先使用, 超限降级到其它引擎
    - 外部配置驱动: 关键词列表、limit、时间窗口、引擎策略
    - 参数化任务: 通过 list_param_jobs() 提供不同 query 参数
    """

    name = "mes.search"
    default_interval_seconds = 300  # 若配置文件里没给，使用该默认

    def __init__(self):
        super().__init__()
        self._loaded = False
        self._query_jobs: list[tuple[str, int, str, Optional[str]]] = (
            []
        )  # (query, interval, engine, time_range)

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
            if not isinstance(data, list):
                logger.warning("unexpected mes output type: %s", type(data))
                return []
            return data  # type: ignore
        except json.JSONDecodeError as e:  # pragma: no cover - 解析异常日志
            logger.error("parse mes json failed query=%s error=%s", query, e)
            return []

    async def fetch(self, param=None) -> AsyncIterator[RawEvent]:  # noqa: D401
        # 若未来 supports_parameters=True, 则 param 可以传入一个 query
        self._ensure_loaded()
        # 若传入单个 param，则只处理该 query；否则全部
        queries = [param] if param else [q for q, _i, _e, _tr in self._query_jobs]
        # 构建 per-query engine/interval/time_range map
        engine_map = {q: eng for q, _i, eng, _tr in self._query_jobs}
        time_range_map = {q: tr for q, _i, _eng, tr in self._query_jobs}
        for q in queries:
            engine = engine_map.get(q) or self._choose_engine(q)
            time_range = time_range_map.get(q)
            results = await self._run_mes(q, engine, time_range)
            for item in results:
                # 结果字段: title, url, description, engine
                url = item.get("url") or ""
                # post_id 用 url 作为去重键 (若缺失则 hash 整个对象)
                raw: Dict[str, Any] = {
                    "post_id": url or json.dumps(item, ensure_ascii=False),
                    "query": q,
                    "title": item.get("title"),
                    "url": url,
                    "description": item.get("description"),
                    "engine": item.get("engine"),
                }
                yield RawEvent(source=self.name, raw=raw)
