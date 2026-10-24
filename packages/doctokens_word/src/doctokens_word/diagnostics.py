"""In-memory parse-content metrics."""

from __future__ import annotations

from .core.metrics import MetricsRecorder
from .core.models import Block, ParsedDocument


def record_content_metrics(parsed_document: ParsedDocument, metrics: MetricsRecorder) -> None:
    """Record node counts used for output budgeting and performance checks."""
    block_stats = _compute_block_stats(parsed_document.blocks)
    metrics.set_counter("blockCount", len(parsed_document.blocks))
    metrics.set_counter("paragraphCount", block_stats["paragraphCount"])
    metrics.set_counter("headingCount", block_stats["headingCount"])
    metrics.set_counter("tableCount", block_stats["tableCount"])
    metrics.set_counter("tableCellCount", block_stats["tableCellCount"])
    metrics.set_counter("runCount", block_stats["runCount"])
    metrics.set_counter("maxTableRows", block_stats["maxTableRows"])
    metrics.set_counter("maxTableCols", block_stats["maxTableCols"])
    metrics.set_counter("relationshipCount", len(parsed_document.relationships))
    metrics.set_counter("styleCount", len(parsed_document.styles))
    metrics.set_counter("assetCount", len(parsed_document.assets))
    metrics.set_counter("chartCount", len(parsed_document.charts))
    metrics.set_counter("smartartCount", len(parsed_document.smartarts))
    metrics.set_counter("ocrResultCount", len(parsed_document.ocr_results))
    metrics.set_counter(
        "ocrErrorCount",
        sum(1 for value in parsed_document.ocr_results.values() if isinstance(value, dict) and value.get("status") == "error"),
    )
    metrics.set_counter("headerCount", len(parsed_document.headers))
    metrics.set_counter("footerCount", len(parsed_document.footers))
    metrics.set_counter("footnoteCount", len(parsed_document.footnotes))
    metrics.set_counter("endnoteCount", len(parsed_document.endnotes))
    metrics.set_counter("commentCount", len(parsed_document.comments))
    metrics.set_counter("warningCount", len(parsed_document.warnings))


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
