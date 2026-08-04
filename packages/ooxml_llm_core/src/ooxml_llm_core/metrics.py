"""Parse-stage timing and statistics."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

from ooxml_llm_core.models import MetricsSnapshot, MetricValue


class MetricsRecorder:
    """Record per-stage timing and lightweight counters for a single document."""

    def __init__(self) -> None:
        self._total_start = perf_counter()
        self.stages_ms: dict[str, float] = {}
        self.counters: dict[str, MetricValue] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        start = perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (perf_counter() - start) * 1000
            self.stages_ms[name] = round(self.stages_ms.get(name, 0.0) + elapsed_ms, 3)

    def set_counter(self, name: str, value: MetricValue) -> None:
        self.counters[name] = value

    def snapshot(self) -> MetricsSnapshot:
        return {
            "totalMs": round((perf_counter() - self._total_start) * 1000, 3),
            "stagesMs": dict(self.stages_ms),
            "counters": dict(self.counters),
        }
