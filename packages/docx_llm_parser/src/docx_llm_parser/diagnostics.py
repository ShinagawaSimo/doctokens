"""Diagnostics, debug artifacts, and parse-content metrics."""

from __future__ import annotations

from dataclasses import asdict

from .core.debug import DebugWriter
from .core.metrics import MetricsRecorder
from .core.models import (
    Block,
    ContentTypes,
    ParsedDocument,
    ParseWarning,
    ZipEntryInfo,
)
from .core.relationships import RelationshipIndex
from .extractors.body import DocumentBodyParser


def write_debug_artifacts(
    debug: DebugWriter,
    zip_index: list[ZipEntryInfo],
    content_types: ContentTypes,
    relationships: RelationshipIndex,
    style_rows: list[dict[str, object]],
    body_parser: DocumentBodyParser,
    parsed: ParsedDocument,
) -> None:
    """Write debug artifacts; append a warning on failure rather than aborting."""
    try:
        debug.write_json(
            "package.json",
            {
                "zipIndex": zip_index,
                "contentTypes": content_types,
                "relationships": relationships.to_debug_list(),
            },
        )
        debug.write_json("styles.json", style_rows)
        debug.write_json("numbering.json", parsed.numbering)
        debug.write_json("blocks.json", parsed.blocks)
        debug.write_json("manifest.json", _debug_manifest(parsed))
        debug.write_jsonl("events.jsonl", body_parser.body_events)
        debug.write_json("warnings.json", [asdict(item) for item in parsed.warnings])
    except Exception as exc:
        parsed.warnings.append(
            ParseWarning(
                code="DEBUG_WRITE_FAILED",
                message=f"Failed to write debug artifacts: {exc}",
            )
        )


def write_metrics_debug(debug: DebugWriter, parsed: ParsedDocument) -> None:
    """Write metrics separately so debug-write timing is persisted."""
    try:
        debug.write_json("metrics.json", parsed.metrics)
    except Exception as exc:
        parsed.warnings.append(
            ParseWarning(
                code="METRICS_WRITE_FAILED",
                message=f"Failed to write metrics debug artifact: {exc}",
            )
        )


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
    metrics.set_counter("headerCount", len(parsed.headers))
    metrics.set_counter("footerCount", len(parsed.footers))
    metrics.set_counter("footnoteCount", len(parsed.footnotes))
    metrics.set_counter("endnoteCount", len(parsed.endnotes))
    metrics.set_counter("commentCount", len(parsed.comments))
    metrics.set_counter("warningCount", len(parsed.warnings))


def _debug_manifest(parsed: ParsedDocument) -> dict[str, object]:
    return {
        "assets": parsed.assets,
        "embedded": {
            "charts": parsed.charts,
            "smartarts": parsed.smartarts,
        },
        "ancillary": {
            "headers": parsed.headers,
            "footers": parsed.footers,
            "footnotes": parsed.footnotes,
            "endnotes": parsed.endnotes,
            "comments": parsed.comments,
        },
        "summary": {
            "blockCount": len(parsed.blocks),
            "assetCount": len(parsed.assets),
            "chartCount": len(parsed.charts),
            "smartartCount": len(parsed.smartarts),
            "headerCount": len(parsed.headers),
            "footerCount": len(parsed.footers),
            "footnoteCount": len(parsed.footnotes),
            "endnoteCount": len(parsed.endnotes),
            "commentCount": len(parsed.comments),
            "styleCount": len(parsed.styles),
            "relationshipCount": len(parsed.relationships),
            "warningCount": len(parsed.warnings),
            "packageInfo": parsed.package_info,
        },
    }


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
