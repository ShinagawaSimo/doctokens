"""In-memory parse-content metrics."""

from __future__ import annotations

from .core.metrics import MetricsRecorder
from .core.models import Block, ParsedDocument


def record_content_metrics(parsed: ParsedDocument, metrics: MetricsRecorder) -> None:
    """Record node counts used for output budgeting and performance checks."""
    stats = _compute_block_stats(parsed.blocks)
    metrics.set_counter("blockCount", len(parsed.blocks))
    metrics.set_counter("paragraphCount", stats["paragraphCount"])
    metrics.set_counter("headingCount", stats["headingCount"])
    metrics.set_counter("tableCount", stats["tableCount"])
    metrics.set_counter("tableCellCount", stats["tableCellCount"])
    metrics.set_counter("runCount", stats["runCount"])
    metrics.set_counter("maxTableRows", stats["maxTableRows"])
    metrics.set_counter("maxTableCols", stats["maxTableCols"])
    metrics.set_counter("relationshipCount", len(parsed.relationships))
    metrics.set_counter("styleCount", len(parsed.styles))
    metrics.set_counter("assetCount", len(parsed.assets))
    metrics.set_counter("chartCount", len(parsed.charts))
    metrics.set_counter("smartartCount", len(parsed.smartarts))
    metrics.set_counter("ocrResultCount", len(parsed.ocr_results))
    metrics.set_counter(
        "ocrErrorCount",
        sum(1 for value in parsed.ocr_results.values() if isinstance(value, dict) and value.get("status") == "error"),
    )
    metrics.set_counter("headerCount", len(parsed.headers))
    metrics.set_counter("footerCount", len(parsed.footers))
    metrics.set_counter("footnoteCount", len(parsed.footnotes))
    metrics.set_counter("endnoteCount", len(parsed.endnotes))
    metrics.set_counter("commentCount", len(parsed.comments))
    metrics.set_counter("warningCount", len(parsed.warnings))


def _compute_block_stats(blocks: list[Block]) -> dict[str, int]:
    stats = {
        "paragraphCount": 0,
        "headingCount": 0,
        "tableCount": 0,
        "tableCellCount": 0,
        "runCount": 0,
        "maxTableRows": 0,
        "maxTableCols": 0,
    }
    for block in blocks:
        if block["type"] == "paragraph":
            stats["paragraphCount"] += 1
            if "runs" in block:
                stats["runCount"] += len(block["runs"])
        elif block["type"] == "heading":
            stats["headingCount"] += 1
            if "runs" in block:
                stats["runCount"] += len(block["runs"])
        elif block["type"] == "table":
            stats["tableCount"] += 1
            stats["maxTableRows"] = max(stats["maxTableRows"], len(block["rows"]))
            stats["maxTableCols"] = max(stats["maxTableCols"], block["columnCount"])
            for row in block["rows"]:
                stats["tableCellCount"] += len(row["cells"])
                for cell in row["cells"]:
                    child_stats = _compute_block_stats(cell["blocks"])
                    for key, value in child_stats.items():
                        if key.startswith("max"):
                            stats[key] = max(stats[key], value)
                        else:
                            stats[key] += value
    return stats
