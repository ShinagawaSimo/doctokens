"""Metrics recording logic for the output renderers.

Per-stage timing and output size are recorded here to avoid duplication
across rendering paths."""

from __future__ import annotations

from pathlib import Path

from ...core.models import ParsedDocument


def record_render_metrics(
    parsed_document: ParsedDocument,
    output_path: Path,
    output_chars: int,
    elapsed_ms: float,
    stage_name: str = "render",
) -> None:
    """Append the final output stage metrics to parsed_document.metrics."""
    metrics = parsed_document.metrics
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
