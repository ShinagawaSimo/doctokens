"""渲染器共享的指标统计逻辑。

两个渲染器（XML/HTML5）都需要记录阶段耗时和输出规模，
此模块提供统一的实现，避免重复。"""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from ..core.models import ParsedDocument, ParseWarning


def record_render_metrics(
    parsed: ParsedDocument,
    output_path: Path,
    output_chars: int,
    elapsed_ms: float,
    stage_name: str = "render",
) -> None:
    """把最终渲染阶段的指标追加到 parsed.metrics。"""
    metrics = parsed.metrics
    stages = metrics.setdefault("stagesMs", {})
    counters = metrics.setdefault("counters", {})
    metrics.setdefault("parseTotalMs", metrics.get("totalMs", 0.0))
    metrics["totalMs"] = round(metrics["parseTotalMs"] + elapsed_ms, 3)
    stages[stage_name] = round(elapsed_ms, 3)
    counters["outputChars"] = output_chars
    counters["outputBytes"] = output_path.stat().st_size
    counters["estimatedTokens"] = max(1, round(output_chars / 4))


def write_metrics_debug(parsed: ParsedDocument) -> None:
    """渲染后重写 metrics.json，包含最终的输出阶段耗时。"""
    if not parsed.debug_dir:
        return
    try:
        path = Path(parsed.debug_dir) / "metrics.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(parsed.metrics, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        parsed.warnings.append(
            ParseWarning(
                level="warning",
                code="METRICS_WRITE_FAILED",
                message=f"Failed to write render metrics debug artifact: {exc}",
            )
        )
