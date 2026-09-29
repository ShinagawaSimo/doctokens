"""Assembly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ooxml_llm_core.models import ParseReport

from .._version import __version__
from ..core.metrics import MetricsRecorder
from ..core.models import (
    AncillaryResult,
    Block,
    Chart,
    ContentTypes,
    ImageAsset,
    OcrStoredResult,
    ParsedDocument,
    ParseWarning,
    SmartArt,
    ZipEntryInfo,
)
from ..core.relationships import RelationshipIndex
from ..diagnostics import record_content_metrics
from ..ooxml.numbering import NumberingMap
from ..ooxml.styles import StyleMap


@dataclass
class _DocumentParseResult:
    """Intermediate results from each pipeline stage, bundled for document assembly."""

    source_path: str | Path | bytes
    source_name: str
    zip_index: list[ZipEntryInfo]
    content_types: ContentTypes
    relationships: RelationshipIndex
    styles: StyleMap
    numbering: NumberingMap
    assets: list[ImageAsset]
    charts: list[Chart]
    smartarts: list[SmartArt]
    blocks: list[Block]
    ancillary: AncillaryResult
    ocr_results: dict[str, OcrStoredResult]
    revision_view: str


def _build_document(
    parse_result: _DocumentParseResult,
    warnings: list[ParseWarning],
    metrics: MetricsRecorder,
) -> ParsedDocument:
    total_uncompressed = 0
    total_compressed = 0
    for zip_entry in parse_result.zip_index:
        total_uncompressed += zip_entry["uncompressedSize"]
        total_compressed += zip_entry["compressedSize"]
    entry_count = len(parse_result.zip_index)
    package_info: dict[str, object] = {
        "entryCount": entry_count,
        "totalUncompressedBytes": total_uncompressed,
        "totalCompressedBytes": total_compressed,
    }
    metrics.set_counter("entryCount", entry_count)
    metrics.set_counter("zipUncompressedBytes", total_uncompressed)
    metrics.set_counter("zipCompressedBytes", total_compressed)
    metadata: dict[str, object] = {
        "sourceFile": parse_result.source_name,
        "sourcePath": (str(parse_result.source_path) if not isinstance(parse_result.source_path, bytes) else ""),
        "format": "docx",
        "parser": "docx_llm_parser",
        "parserVersion": __version__,
        "revisionView": parse_result.revision_view,
    }

    parsed_document = ParsedDocument(
        metadata=metadata,
        package_info=package_info,
        blocks=parse_result.blocks,
        relationships=list(parse_result.relationships.records),
        styles=list(parse_result.styles.records.values()),
        warnings=warnings,
        content_types=parse_result.content_types,
        assets=parse_result.assets,
        charts=parse_result.charts,
        smartarts=parse_result.smartarts,
        headers=parse_result.ancillary["headers"],
        footers=parse_result.ancillary["footers"],
        footnotes=parse_result.ancillary["footnotes"],
        endnotes=parse_result.ancillary["endnotes"],
        comments=parse_result.ancillary["comments"],
        ocr_results=parse_result.ocr_results,
    )
    record_content_metrics(parsed_document, metrics)
    parsed_document.metrics = metrics.snapshot()
    parsed_document.report = ParseReport(
        "docx",
        1,
        {
            "pageCount": max((block.get("page", 1) for block in parsed_document.blocks), default=1),
            "blockCount": len(parsed_document.blocks),
            "tableCount": sum(1 for block in parsed_document.blocks if block["type"] == "table"),
            "imageCount": len(parsed_document.assets),
            "chartCount": len(parsed_document.charts),
            "smartartCount": len(parsed_document.smartarts),
            "commentCount": len(parsed_document.comments),
        },
        tuple(parsed_document.warnings),
        parsed_document.metrics,
    )
    return parsed_document
