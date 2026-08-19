"""Metrics recording logic for the HTML5 renderers.

Per-stage timing and output size are recorded here to avoid duplication
across rendering paths."""

from __future__ import annotations

import json
from pathlib import Path

from ...core.models import ParsedDocument, ParseWarning


def record_render_metrics(
    parsed: ParsedDocument,
    output_path: Path,
    output_chars: int,
    elapsed_ms: float,
    stage_name: str = "render",
) -> None:
    """Append the final render stage metrics to parsed.metrics."""
    metrics = parsed.metrics
    if "stagesMs" not in metrics:
        metrics["stagesMs"] = {}
    if "counters" not in metrics:
        metrics["counters"] = {}
    if "parseTotalMs" not in metrics:
        metrics["parseTotalMs"] = metrics.get("totalMs", 0.0)

    stages = metrics["stagesMs"]
    counters = metrics["counters"]
    metrics["totalMs"] = round(metrics["parseTotalMs"] + elapsed_ms, 3)
    stages[stage_name] = round(elapsed_ms, 3)
    counters["outputChars"] = output_chars
    counters["outputBytes"] = output_path.stat().st_size
    counters["estimatedTokens"] = max(1, round(output_chars / 4))


def write_metrics_debug(parsed: ParsedDocument) -> None:
    """Rewrite metrics.json after rendering, including the final output stage timing."""
    if not parsed.debug_dir:
        return
    try:
        path = Path(parsed.debug_dir) / "metrics.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(parsed.metrics, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        parsed.warnings.append(
            ParseWarning(
                code="METRICS_WRITE_FAILED",
                message=f"Failed to write render metrics debug artifact: {exc}",
            )
        )
