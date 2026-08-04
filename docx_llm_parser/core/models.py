"""解析器内部数据模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, TypedDict

from .enums import RevisionMode


class ZipEntryInfo(TypedDict):
    """Security-relevant metadata for one ZIP package entry."""

    name: str
    compressedSize: int
    uncompressedSize: int
    crc: int


class ContentTypes(TypedDict):
    """OPC content type mappings keyed by extension and part name."""

    defaults: dict[str, str]
    overrides: dict[str, str]


JsonObject = dict[str, object]
RunFormat = dict[str, bool | str | None]


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


class ChartSeriesRequired(TypedDict):
    index: int
    pointCount: int
    preview: str


class ChartSeries(ChartSeriesRequired, total=False):
    """Compact data summary for one chart series."""

    name: str
    min: float
    max: float
    formula: str


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

    preserveSpace: bool
    objects: list[InlineObject]
    styleId: str
    format: RunFormat
    link: LinkInfo
    revision: Literal["inserted", "deleted"]
    kind: str


RawHint = JsonObject | InlineObject


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


ResourceSummary = dict[str, object]
ResourceDetail = dict[str, object]
MetricValue = int | float | str


class MetricsSnapshot(TypedDict, total=False):
    """Parse/render timing and size counters safe to serialize as JSON."""

    totalMs: float
    parseTotalMs: float
    stagesMs: dict[str, float]
    counters: dict[str, MetricValue]


@dataclass(frozen=True)
class ParseOptions:
    """解析配置；设为不可变，避免并发任务互相污染。"""

    preserve_empty_paragraphs: bool = False
    include_runs: bool = True
    include_raw_hints: bool = True
    debug: bool = False
    revision_mode: RevisionMode = RevisionMode.FINAL
    output_dir: Path = Path("out")
    max_zip_entries: int = 10000
    max_entry_uncompressed_bytes: int = 50 * 1024 * 1024
    max_total_uncompressed_bytes: int = 500 * 1024 * 1024

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


@dataclass(slots=True)
class ParseWarning:
    """解析过程中可恢复问题的记录。"""

    code: str
    message: str
    locator: str = ""


@dataclass(slots=True)
class RelationshipRecord:
    """OPC relationship 记录。"""

    source_part: str
    id: str
    type: str
    target: str
    target_mode: str | None = None
    resolved_target: str | None = None


@dataclass(slots=True)
class StyleRecord:
    """Word 样式摘要。"""

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
    """内部完整解析结果；最终输出会再精简。"""

    metadata: dict[str, object]
    package_info: dict[str, object]
    blocks: list[Block]
    relationships: list[RelationshipRecord]
    styles: list[StyleRecord]
    warnings: list[ParseWarning]
    debug_dir: str | None = None
    content_types: ContentTypes = field(
        default_factory=lambda: ContentTypes(defaults={}, overrides={})
    )
    assets: list[ImageAsset] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)
    smartarts: list[SmartArt] = field(default_factory=list)
    headers: list[AncillaryItem] = field(default_factory=list)
    footers: list[AncillaryItem] = field(default_factory=list)
    footnotes: list[AncillaryItem] = field(default_factory=list)
    endnotes: list[AncillaryItem] = field(default_factory=list)
    comments: list[AncillaryItem] = field(default_factory=list)
    numbering: dict[str, object] = field(default_factory=dict)
    metrics: MetricsSnapshot = field(
        default_factory=lambda: MetricsSnapshot(stagesMs={}, counters={})
    )

    def to_dict(self) -> dict[str, object]:
        """输出内部完整结构，主要供 debug 或开发检查使用。"""
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
            "metrics": self.metrics,
        }
