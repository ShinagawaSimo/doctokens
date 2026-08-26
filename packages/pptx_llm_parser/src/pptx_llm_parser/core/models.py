"""PPTX parse models: options and parsed presentation structure."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, TypedDict

from ooxml_llm_core.chart_ml import ChartPlotInfo, ChartSeriesInfo
from ooxml_llm_core.models import MetricsSnapshot, ParseReport, ParseWarning
from ooxml_llm_core.options import PackageOptions

DEFAULT_MAX_ZIP_ENTRIES = 10_000
DEFAULT_MAX_ENTRY_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES = 500 * 1024 * 1024


def _empty_metrics() -> MetricsSnapshot:
    return {}


@dataclass(frozen=True)
class ParseOptions(PackageOptions):
    """Tunables for a single parse. Frozen so callers can share one instance safely."""

    ocr: object | None = None
    ocr_workers: int = 4
    ocr_timeout: float = 120.0

    def __post_init__(self) -> None:
        self.validate_package_options()
        self.validate_ocr_options(self.ocr, self.ocr_workers, self.ocr_timeout)


class RunFormat(TypedDict, total=False):
    """Visual formats on a text run."""

    bold: bool
    italic: bool
    underline: bool
    color: str


class Run(TypedDict, total=False):
    """One text run inside a text shape."""

    text: str
    format: RunFormat
    link: str
    equation: str


class Paragraph(TypedDict, total=False):
    """One DrawingML paragraph, including list metadata."""

    text: str
    level: int
    bullet: str
    numberType: str
    startAt: int


class ParagraphStyle(TypedDict, total=False):
    """Resolved paragraph defaults inherited from master/layout/list style."""

    runFormat: RunFormat
    bullet: str
    numberType: str
    startAt: int


class TableCell(TypedDict, total=False):
    """A table cell with the OOXML merge declarations preserved."""

    text: str
    colSpan: int
    rowSpan: int
    hMerge: bool
    vMerge: bool


class ShapeBlock(TypedDict, total=False):
    """One shape on a slide; ``z`` records XML stacking order."""

    id: str
    type: str
    name: str
    text: str
    assetId: str
    alt: str
    title: str
    href: str
    link: str
    kind: str
    geometryType: str
    fromShape: str
    toShape: str
    rows: list[list[str]]
    tableCells: list[list[TableCell]]
    columnWidths: list[int]
    paragraphs: list[Paragraph]
    tableId: str
    chartId: str
    chartType: str
    seriesCount: int
    pointCount: int
    smartartId: str
    layoutType: str
    nodeCount: int
    linkCount: int
    placeholderType: str
    x: int
    y: int
    w: int
    h: int
    z: int
    runs: list[Run]


class ImageAsset(TypedDict, total=False):
    """Metadata for an embedded or external image/media part (no binary data)."""

    id: str
    type: str
    source: str
    href: str
    contentType: str
    zipPath: str
    file: str


AssetLookup = dict[tuple[str, str], ImageAsset]


class OcrResultRecord(TypedDict, total=False):
    """Stored OCR outcome; provider diagnostics stay out of rendered output."""

    status: Literal["success", "empty", "error"]
    text: str
    error_code: str
    error_message: str


OcrStoredResult = str | OcrResultRecord


class SmartArtNode(TypedDict):
    id: int
    text: str


SmartArtLink = TypedDict("SmartArtLink", {"from": int, "to": int})


class ChartRecord(TypedDict, total=False):
    """ChartML record produced by the shared chart_ml parser plus locator fields."""

    id: str
    part: str
    chart_type: str
    title: str
    series: list[ChartSeriesInfo]
    series_count: int
    point_count: int
    plots: list[ChartPlotInfo]


class SmartArtRecord(TypedDict, total=False):
    """Diagram data model with 1-based node ordinals."""

    id: str
    part: str
    nodes: list[SmartArtNode]
    links: list[SmartArtLink]
    nodeCount: int
    linkCount: int
    layoutType: str


ChartLookup = Mapping[tuple[str, str], ChartRecord]
SmartArtLookup = Mapping[tuple[str, str], SmartArtRecord]
LayoutLookup = dict[tuple[str, str], str]


class PlaceholderInfo(TypedDict, total=False):
    """Placeholder declaration from a layout, geometry resolved two levels up."""

    type: str
    x: int
    y: int
    w: int
    h: int


class LayoutContext(TypedDict):
    """Per-slide inheritance resolution products."""

    theme: dict[str, str]
    placeholders: dict[str, PlaceholderInfo]
    color_map: dict[str, str]
    text_styles: dict[str, dict[int, ParagraphStyle]]


class SlideBackground(TypedDict, total=False):
    color: str
    assetId: str


class CommentRef(TypedDict, total=False):
    id: str
    shapeId: str


class SlideBlock(TypedDict):
    """One slide in presentation order (sldIdLst)."""

    id: str
    type: str
    n: int
    part: str
    sldId: str
    hidden: bool
    shapes: list[ShapeBlock]
    notes: str | None
    background: SlideBackground | None
    commentRefs: list[CommentRef]
    section: str | None


class PresentationSection(TypedDict):
    """A named PowerPoint section and the presentation slide IDs it contains."""

    name: str
    slideIds: list[str]


class CommentItem(TypedDict, total=False):
    """A modern threaded comment with author and thread linkage."""

    id: str
    text: str
    author: str
    date: str
    parentId: str
    parentCommentId: str
    slideId: str
    shapeId: str
    x: int
    y: int


@dataclass
class ParsedPresentation:
    """All parse products for one presentation."""

    slides: list[SlideBlock] = field(default_factory=list)
    slide_size: tuple[int, int] | None = None
    assets: list[ImageAsset] = field(default_factory=list)
    charts: list[ChartRecord] = field(default_factory=list)
    smartarts: list[SmartArtRecord] = field(default_factory=list)
    theme: dict[str, str] = field(default_factory=dict)
    comments: list[CommentItem] = field(default_factory=list)
    sections: list[PresentationSection] = field(default_factory=list)
    warnings: list[ParseWarning] = field(default_factory=list)
    ocr_results: dict[str, OcrStoredResult] = field(default_factory=dict)
    metrics: MetricsSnapshot = field(default_factory=_empty_metrics)
    report: ParseReport | None = None
