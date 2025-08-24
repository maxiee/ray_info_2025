from __future__ import annotations

import asyncio
import random
from typing import AsyncIterator
from ..base import SimpleCollector, RawEvent


class WeiboHomeCollector(SimpleCollector):
    name = "weibo.home"
    default_interval_seconds = 60

    async def fetch(self, param=None) -> AsyncIterator[RawEvent]:  # noqa: D401
        await asyncio.sleep(0.05)
        for i in range(random.randint(1, 3)):
            yield RawEvent(
                source=self.name,
                raw={
                    "post_id": f"sim_{random.randint(1000,9999)}",
                    "text": f"模拟微博首页内容 {i}",
                },
                debug=True,
            )
