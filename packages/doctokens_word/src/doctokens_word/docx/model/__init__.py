"""Public DOCX IR exports grouped by content, structure, and document scope."""

from __future__ import annotations

from doctokens_core.containers.opc.locator import part_block_locator
from doctokens_core.containers.opc.models import ContentTypes, RelationshipRecord, ZipEntryInfo
from doctokens_core.contracts.models import JsonObject, MetricsSnapshot, MetricValue, ParseWarning

from .blocks import (
    AncillaryContent,
    AncillaryItem,
    AncillaryResult,
    Block,
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
    ParagraphBorder,
    ParagraphBorders,
    RawHint,
    Run,
    RunFormat,
    SmartArt,
    SmartArtLink,
    SmartArtNode,
)
from .document import DocumentManifest, OcrResultRecord, ParsedDocument, ParseOptions, StyleRecord


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
    "ParagraphBlock",
    "ParagraphBorder",
    "ParagraphBorders",
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
