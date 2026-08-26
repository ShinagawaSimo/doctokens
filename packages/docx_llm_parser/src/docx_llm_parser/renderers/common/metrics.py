"""Metrics recording logic for the HTML5 renderers.

Per-stage timing and output size are recorded here to avoid duplication
across rendering paths."""

from __future__ import annotations

from pathlib import Path

from ...core.models import ParsedDocument


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
