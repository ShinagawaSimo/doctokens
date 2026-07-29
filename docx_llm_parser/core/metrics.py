"""解析阶段级计时和统计。"""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any, Iterator


class MetricsRecorder:
    """记录单篇文档解析的阶段耗时和轻量统计。"""

    def __init__(self) -> None:
        self._total_start = perf_counter()
        self.stages_ms: dict[str, float] = {}
        self.counters: dict[str, Any] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """记录一个阶段的耗时；同名阶段会累加。"""
        start = perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (perf_counter() - start) * 1000
            self.stages_ms[name] = round(self.stages_ms.get(name, 0.0) + elapsed_ms, 3)

    def set_counter(self, name: str, value: Any) -> None:
        """写入计数或大小类指标。"""
        self.counters[name] = value

    def snapshot(self) -> dict[str, Any]:
        """生成可写入 debug 的 metrics 快照。"""
        return {
            "totalMs": round((perf_counter() - self._total_start) * 1000, 3),
            "stagesMs": dict(self.stages_ms),
            "counters": dict(self.counters),
        }
