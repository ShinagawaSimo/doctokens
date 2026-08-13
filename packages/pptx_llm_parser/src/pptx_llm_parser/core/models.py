"""PPTX parse models: options and parsed presentation structure."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from ooxml_llm_core.chart_ml import ChartSeriesInfo
from ooxml_llm_core.models import ParseWarning

DEFAULT_MAX_ZIP_ENTRIES = 10_000
DEFAULT_MAX_ENTRY_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES = 500 * 1024 * 1024


@dataclass(frozen=True)
class ParseOptions:
    """Tunables for a single parse. Frozen so callers can share one instance safely."""

    debug: bool = False
    output_dir: Path = field(default_factory=lambda: Path("out"))
    max_zip_entries: int = DEFAULT_MAX_ZIP_ENTRIES
    max_entry_uncompressed_bytes: int = DEFAULT_MAX_ENTRY_UNCOMPRESSED_BYTES
    max_total_uncompressed_bytes: int = DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES

    def __post_init__(self) -> None:
        for name in (
            "max_zip_entries",
            "max_entry_uncompressed_bytes",
            "max_total_uncompressed_bytes",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be greater than zero")


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


class ShapeBlock(TypedDict, total=False):
    """One shape on a slide, in XML (z-order) sequence."""

    id: str
    type: str
    name: str
    text: str
    assetId: str
    alt: str
    href: str
    kind: str
    rows: list[list[str]]
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


class SmartArtRecord(TypedDict, total=False):
    """Diagram data model with 1-based node ordinals."""

    id: str
    part: str
    nodes: list[SmartArtNode]
    links: list[SmartArtLink]
    nodeCount: int
    linkCount: int


ChartLookup = dict[tuple[str, str], ChartRecord]
SmartArtLookup = dict[tuple[str, str], SmartArtRecord]
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

    placeholders: dict[str, PlaceholderInfo]
    color_map: dict[str, str]


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


class CommentItem(TypedDict, total=False):
    """A modern threaded comment with author and thread linkage."""

    id: str
    text: str
    author: str
    date: str
    parentId: str


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
    warnings: list[ParseWarning] = field(default_factory=list)
