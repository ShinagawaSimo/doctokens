"""Parser internal data model - DOCX-specific types + shared type re-exports."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, TypedDict

from ooxml_llm_core.models import (
    ContentTypes,
    JsonObject,
    MetricsSnapshot,
    MetricValue,
    ParseWarning,
    RelationshipRecord,
    ZipEntryInfo,
)

from .enums import RevisionMode
from .locator import part_block_locator

RunFormat = dict[str, bool | str | None]


def append_warning(
    warnings: list[ParseWarning],
    code: str,
    message: str,
    *,
    part: str | None = None,
    block_id: str | None = None,
) -> None:
    """Append a parse warning with the standard part:block locator shape."""
    warnings.append(
        ParseWarning(
            code=code,
            message=message,
            locator=part_block_locator(part, block_id),
        )
    )


class LinkInfo(TypedDict, total=False):
    """Hyperlink target attached to a text run."""

    href: str
    anchor: str


class NumberingLabel(TypedDict):
    """Visible numbering prefix attached to one paragraph."""

    numId: str
    level: int
    label: str
    text: str
    format: str
    template: str | None
    suffix: str
    counter: int


class ImageAssetRequired(TypedDict):
    id: str
    type: Literal["image"]
    source: Literal["external", "embedded"]


class ImageAsset(ImageAssetRequired, total=False):
    """Image referenced by the document. Binary data retrieved via get_resource."""

    href: str
    contentType: str
    zipPath: str
    file: str


class ChartSeriesRequired(TypedDict):
    index: int
    pointCount: int
    preview: str


class ChartSeries(ChartSeriesRequired, total=False):
    """Full data for one chart series."""

    name: str
    min: float
    max: float
    formula: str
    categories: list[str]  # full category labels (for get_resource)
    values: list[str]  # full cached values (for get_resource)


class ChartRequired(TypedDict):
    id: str
    type: Literal["chart"]
    chartType: str
    part: str
    seriesCount: int
    pointCount: int
    series: list[ChartSeries]


class Chart(ChartRequired, total=False):
    """Parsed chart data linked to an inline chart reference."""

    title: str
    sourcePart: str
    relationshipId: str


class SmartArtNodeRequired(TypedDict):
    modelId: str
    text: str


class SmartArtNode(SmartArtNodeRequired, total=False):
    kind: str


SmartArtLinkRequired = TypedDict("SmartArtLinkRequired", {"from": int, "to": int})


class SmartArtLink(SmartArtLinkRequired, total=False):
    kind: str


class SmartArtRequired(TypedDict):
    id: str
    type: Literal["smartart"]
    part: str
    nodeCount: int
    linkCount: int
    rawLinkCount: int
    nodes: list[SmartArtNode]
    links: list[SmartArtLink]


class SmartArt(SmartArtRequired, total=False):
    """Parsed SmartArt graph linked to an inline diagram reference."""

    layoutType: str
    sourcePart: str
    relationshipId: str


AssetLookup = dict[tuple[str, str], ImageAsset]
ObjectLookup = dict[tuple[str, str], Chart | SmartArt]


class DrawingCommon(TypedDict, total=False):
    """Shared DrawingML/VML metadata copied onto inline objects."""

    placement: str
    name: str
    alt: str
    title: str
    cx: str
    cy: str


class InlineObjectRequired(TypedDict):
    type: str


class InlineObject(InlineObjectRequired, total=False):
    """Inline non-text object carried by a run."""

    id: str | None
    assetId: str
    file: str
    embeddedType: str
    progid: str
    href: str
    alt: str
    name: str
    title: str
    placement: str
    cx: str
    cy: str
    text: str
    instruction: str
    chartType: str
    part: str
    seriesCount: int
    pointCount: int
    series: list[ChartSeries]
    nodeCount: int
    linkCount: int
    rawLinkCount: int
    nodes: list[SmartArtNode]
    links: list[SmartArtLink]
    layoutType: str
    sourcePart: str
    relationshipId: str


class RunRequired(TypedDict):
    text: str


class Run(RunRequired, total=False):
    """Visible text run plus optional formatting, links and inline objects."""

    objects: list[InlineObject]
    styleId: str
    format: RunFormat
    link: LinkInfo
    revision: Literal["inserted", "deleted"]


RawHint = dict[str, object] | InlineObject


class ParagraphBlockRequired(TypedDict):
    id: str
    type: Literal["paragraph"]
    part: str
    order: int
    page: int
    styleId: str | None
    text: str


class ParagraphBlock(ParagraphBlockRequired, total=False):
    runs: list[Run]
    rawHints: list[RawHint]
    numbering: NumberingLabel


class HeadingBlockRequired(TypedDict):
    id: str
    type: Literal["heading"]
    part: str
    order: int
    page: int
    styleId: str | None
    text: str
    level: int
    headingSource: Literal["style"]


class HeadingBlock(HeadingBlockRequired, total=False):
    runs: list[Run]
    rawHints: list[RawHint]
    numbering: NumberingLabel


TextBlock = ParagraphBlock | HeadingBlock


class TableCellRequired(TypedDict):
    rowIndex: int
    colIndex: int
    rowSpan: int
    colSpan: int
    text: str
    blocks: list[Block]


class TableCell(TableCellRequired, total=False):
    vMerge: str


class TableRowRequired(TypedDict):
    rowIndex: int
    cells: list[TableCell]


class TableRow(TableRowRequired, total=False):
    isHeader: bool


class TableBlock(TypedDict):
    id: str
    type: Literal["table"]
    part: str
    order: int
    page: int
    tableId: str
    segmentIndex: int
    rows: list[TableRow]
    columnCount: int


Block = TextBlock | TableBlock


class BodyEventRequired(TypedDict):
    id: str
    type: str
    order: int
    part: str


class BodyEvent(BodyEventRequired, total=False):
    textPreview: str
    numberingLabel: str
    level: int
    rowCount: int
    columnCount: int


class AncillaryContent(TypedDict):
    text: str
    runs: list[Run]
    rawHints: list[RawHint]


class AncillaryItemRequired(TypedDict):
    id: str | None
    loc: str
    text: str
    runs: list[Run]


class AncillaryItem(AncillaryItemRequired, total=False):
    rawHints: list[RawHint]
    author: str | None
    date: str | None


class AncillaryResult(TypedDict):
    headers: list[AncillaryItem]
    footers: list[AncillaryItem]
    footnotes: list[AncillaryItem]
    endnotes: list[AncillaryItem]
    comments: list[AncillaryItem]


InlineContainer = TextBlock | AncillaryItem


class DocumentManifest(TypedDict):
    """Small document overview returned before rendering or resource extraction."""

    pages: int
    tables: int
    images: int
    footnotes: int
    endnotes: int
    comments: int


class OcrResultRecord(TypedDict, total=False):
    """Stored OCR outcome; status is success, empty, or error."""

    status: Literal["success", "empty", "error"]
    text: str
    error_code: str
    error_message: str


OcrStoredResult = str | OcrResultRecord


ResourceSummary = dict[str, object]
ResourceDetail = dict[str, object]


@dataclass(frozen=True)
class ParseOptions:
    """Parse configuration; immutable to keep concurrent tasks from interfering with each other."""

    preserve_empty_paragraphs: bool = False
    include_runs: bool = True
    include_raw_hints: bool = True
    debug: bool = False
    revision_mode: RevisionMode = RevisionMode.FINAL
    output_dir: Path = Path("out")
    max_zip_entries: int = 10000
    max_entry_uncompressed_bytes: int = 50 * 1024 * 1024
    max_total_uncompressed_bytes: int = 500 * 1024 * 1024
    ocr: object | None = None  # OcrProvider | None, lazy import
    ocr_workers: int = 4
    ocr_timeout: float = 120.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "revision_mode", RevisionMode.parse(self.revision_mode))
        limits = {
            "max_zip_entries": self.max_zip_entries,
            "max_entry_uncompressed_bytes": self.max_entry_uncompressed_bytes,
            "max_total_uncompressed_bytes": self.max_total_uncompressed_bytes,
        }
        for name, value in limits.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if isinstance(self.ocr_workers, bool) or not isinstance(self.ocr_workers, int) or self.ocr_workers <= 0:
            raise ValueError("ocr_workers must be greater than zero")
        if (
            isinstance(self.ocr_timeout, bool)
            or not isinstance(self.ocr_timeout, (int, float))
            or not math.isfinite(self.ocr_timeout)
            or self.ocr_timeout <= 0
        ):
            raise ValueError("ocr_timeout must be greater than zero")
        if self.ocr is not None and not any(
            callable(getattr(self.ocr, method, None)) for method in ("extract", "extract_result")
        ):
            raise TypeError("ocr must provide an extract(image_bytes) or extract_result(image_bytes) method")


@dataclass(slots=True)
class StyleRecord:
    """Word style summary."""

    style_id: str
    type: str = "unknown"
    name: str | None = None
    based_on: str | None = None
    next: str | None = None
    outline_level: int | None = None
    numbering_num_id: str | None = None
    numbering_level: int | None = None
    run_format: RunFormat = field(default_factory=dict)
    is_default: bool = False
    resolved_heading_level: int | None = None


@dataclass
class ParsedDocument:
    """Full internal parse result; the final output is further reduced."""

    metadata: dict[str, object]
    package_info: dict[str, object]
    blocks: list[Block]
    relationships: list[RelationshipRecord]
    styles: list[StyleRecord]
    warnings: list[ParseWarning]
    debug_dir: str | None = None
    content_types: ContentTypes = field(default_factory=lambda: ContentTypes(defaults={}, overrides={}))
    assets: list[ImageAsset] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)
    smartarts: list[SmartArt] = field(default_factory=list)
    headers: list[AncillaryItem] = field(default_factory=list)
    footers: list[AncillaryItem] = field(default_factory=list)
    footnotes: list[AncillaryItem] = field(default_factory=list)
    endnotes: list[AncillaryItem] = field(default_factory=list)
    comments: list[AncillaryItem] = field(default_factory=list)
    numbering: dict[str, object] = field(default_factory=dict)
    ocr_results: dict[str, OcrStoredResult] = field(default_factory=dict)
    metrics: MetricsSnapshot = field(default_factory=lambda: MetricsSnapshot(stagesMs={}, counters={}))

    def to_dict(self) -> dict[str, object]:
        """Output the full internal structure, mainly for debug or development inspection."""
        return {
            "metadata": self.metadata,
            "packageInfo": self.package_info,
            "blocks": self.blocks,
            "relationships": [asdict(item) for item in self.relationships],
            "styles": [asdict(item) for item in self.styles],
            "warnings": [asdict(item) for item in self.warnings],
            "debugDir": self.debug_dir,
            "contentTypes": self.content_types,
            "assets": self.assets,
            "charts": self.charts,
            "smartarts": self.smartarts,
            "headers": self.headers,
            "footers": self.footers,
            "footnotes": self.footnotes,
            "endnotes": self.endnotes,
            "comments": self.comments,
            "numbering": self.numbering,
            "ocrResults": self.ocr_results,
            "metrics": self.metrics,
        }


__all__ = [
    "AncillaryContent",
    "AncillaryItem",
    "AncillaryResult",
    "AssetLookup",
    "Block",
    "BodyEvent",
    "Chart",
    "ChartSeries",
    "ContentTypes",
    "DocumentManifest",
    "DrawingCommon",
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
    "ResourceDetail",
    "ResourceSummary",
    "Run",
    "RunFormat",
    "SmartArt",
    "SmartArtLink",
    "SmartArtNode",
    "StyleRecord",
    "TableBlock",
    "TableCell",
    "TableRow",
    "TextBlock",
    "ZipEntryInfo",
]
