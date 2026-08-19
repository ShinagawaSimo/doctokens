"""Public DOCX IR exports grouped by content, structure, and document scope."""

from __future__ import annotations

from ooxml_llm_core.models import (
    ContentTypes,
    JsonObject,
    MetricsSnapshot,
    MetricValue,
    ParseWarning,
    RelationshipRecord,
    ZipEntryInfo,
)

from ..locator import part_block_locator
from .blocks import (
    AncillaryContent,
    AncillaryItem,
    AncillaryResult,
    Block,
    BodyEvent,
    HeadingBlock,
    InlineContainer,
    NumberingLabel,
    ParagraphBlock,
    TableBlock,
    TableBlockRequired,
    TableCell,
    TableRow,
    TextBlock,
)
from .content import (
    AssetLookup,
    Chart,
    ChartPlot,
    ChartSeries,
    ContentControl,
    ContentControlOption,
    DrawingCommon,
    FieldInfo,
    ImageAsset,
    InlineObject,
    LinkInfo,
    ObjectLookup,
    RawHint,
    Run,
    RunFormat,
    SmartArt,
    SmartArtLink,
    SmartArtNode,
)
from .document import DocumentManifest, OcrResultRecord, OcrStoredResult, ParsedDocument, ParseOptions, StyleRecord


def append_warning(
    warnings: list[ParseWarning],
    code: str,
    message: str,
    *,
    part: str | None = None,
    block_id: str | None = None,
) -> None:
    """Append a parse warning with the standard part:block locator shape."""
    warnings.append(ParseWarning(code=code, message=message, locator=part_block_locator(part, block_id)))


__all__ = [
    "AncillaryContent",
    "AncillaryItem",
    "AncillaryResult",
    "AssetLookup",
    "Block",
    "BodyEvent",
    "Chart",
    "ChartPlot",
    "ChartSeries",
    "ContentControl",
    "ContentControlOption",
    "ContentTypes",
    "DocumentManifest",
    "DrawingCommon",
    "FieldInfo",
    "HeadingBlock",
    "ImageAsset",
    "InlineContainer",
    "InlineObject",
    "JsonObject",
    "LinkInfo",
    "MetricValue",
    "MetricsSnapshot",
    "NumberingLabel",
    "ObjectLookup",
    "OcrResultRecord",
    "OcrStoredResult",
    "ParagraphBlock",
    "ParseOptions",
    "ParseWarning",
    "ParsedDocument",
    "RawHint",
    "RelationshipRecord",
    "Run",
    "RunFormat",
    "SmartArt",
    "SmartArtLink",
    "SmartArtNode",
    "StyleRecord",
    "TableBlock",
    "TableBlockRequired",
    "TableCell",
    "TableRow",
    "TextBlock",
    "ZipEntryInfo",
    "append_warning",
]
