from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, List, Dict, Any

from ..base import BaseCollector, RawEvent

logger = logging.getLogger("rayinfo.collector.mes")


class MesCollector(BaseCollector):
    """使用外部 `mes` CLI 进行多搜索引擎查询的采集器.

    当前实现：
    - 固定关键词列表（示例）与固定搜索引擎 (duckduckgo)
    - 运行: mes search <query> --output json --limit N
    - 将每条结果转换为 RawEvent (post_id 使用结果 url 便于去重)

    未来扩展预留：
    - _choose_engine(): 支持 Google API 配额内优先使用, 超限降级到其它引擎
    - 外部配置驱动: 关键词列表、limit、时间窗口、引擎策略
    - 参数化任务: supports_parameters=True 后由调度器传入不同 query 参数
    """

    name = "mes.search"
    supports_parameters = False  # 未来可改 True 支持传入 query 参数
    default_interval_seconds = 300  # 默认 5 分钟执行一次

    # 简单示例关键词; 实际可改为配置加载
    _queries: List[str] = ["机器学习", "人工智能 新闻"]

    async def setup(self) -> None:  # 可选初始化, 这里暂无
        return None

    def _choose_engine(self, query: str) -> str:
        """预留搜索引擎选择策略.

        当前直接返回 "duckduckgo". 未来可：
        1. 若 Google API 配额剩余 -> 返回 google
        2. 否则 fallback 到 duckduckgo / bing / searx
        """
        return "duckduckgo"

    async def _run_mes(self, query: str, engine: str) -> list[dict[str, Any]]:
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
        queries = [param] if param else self._queries
        for q in queries:
            engine = self._choose_engine(q)
            results = await self._run_mes(q, engine)
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
