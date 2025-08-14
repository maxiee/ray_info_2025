from __future__ import annotations

from ..collectors.base import RawEvent


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
    def process(self, events: list[RawEvent]) -> list[RawEvent]:
        for e in events:
            print(f"[Persist] {e.source} {e.raw}")
        return events


class Pipeline:
    def __init__(self, stages: list[PipelineStage]):
        self.stages = stages

    def run(self, events: list[RawEvent]) -> list[RawEvent]:
        data = events
        for st in self.stages:
            data = st.process(data)
        return data
