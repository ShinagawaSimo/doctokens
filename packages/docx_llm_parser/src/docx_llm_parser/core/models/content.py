"""Content-level DOCX model types: assets, objects, runs, and controls."""

from __future__ import annotations

from typing import Literal, TypedDict

RunFormat = dict[str, bool | str | None]


class ParagraphBorder(TypedDict, total=False):
    style: str
    color: str
    size: str


ParagraphBorders = dict[str, ParagraphBorder]


class LinkInfo(TypedDict, total=False):
    href: str
    anchor: str


class FieldInfo(TypedDict, total=False):
    kind: Literal["citation", "reference"]
    key: str
    anchor: str


class ContentControlOption(TypedDict, total=False):
    display: str
    value: str


class ContentControl(TypedDict, total=False):
    type: Literal["contentControl"]
    controlType: str
    id: str
    tag: str
    alias: str
    lock: str
    placeholder: str
    binding: dict[str, str]
    options: list[ContentControlOption]
    checked: bool
    dateFormat: str
    multiLine: bool
    temporary: bool


class ImageAssetRequired(TypedDict):
    id: str
    type: Literal["image"]
    source: Literal["external", "embedded"]


class ImageAsset(ImageAssetRequired, total=False):
    href: str
    contentType: str
    zipPath: str
    file: str


class ChartSeriesRequired(TypedDict):
    index: int
    pointCount: int
    preview: str


class ChartSeries(ChartSeriesRequired, total=False):
    name: str
    min: float
    max: float
    formula: str
    categories: list[str]
    values: list[str]
    plotIndex: int
    chartType: str
    xValues: list[str]
    yValues: list[str]
    bubbleSizes: list[str]
    categoryFormula: str
    hidden: bool


class ChartPlot(TypedDict, total=False):
    index: int
    chartType: str
    seriesIndices: list[int]


class ChartRequired(TypedDict):
    id: str
    type: Literal["chart"]
    chartType: str
    part: str
    seriesCount: int
    pointCount: int
    series: list[ChartSeries]


class Chart(ChartRequired, total=False):
    title: str
    sourcePart: str
    relationshipId: str
    plots: list[ChartPlot]


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
    layoutType: str
    sourcePart: str
    relationshipId: str


AssetLookup = dict[tuple[str, str], ImageAsset]
ObjectLookup = dict[tuple[str, str], Chart | SmartArt]


class DrawingCommon(TypedDict, total=False):
    placement: str
    name: str
    alt: str
    title: str
    cx: str
    cy: str


class InlineObjectRequired(TypedDict):
    type: str


class InlineObject(InlineObjectRequired, total=False):
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
    plots: list[ChartPlot]
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
    objects: list[InlineObject]
    styleId: str
    format: RunFormat
    link: LinkInfo
    revision: Literal["inserted", "deleted"]
    revisionAuthor: str
    revisionDate: str
    field: FieldInfo
    contentControls: list[ContentControl]


RawHint = dict[str, object] | InlineObject


__all__ = [
    "AssetLookup",
    "Chart",
    "ChartPlot",
    "ChartSeries",
    "ContentControl",
    "ContentControlOption",
    "DrawingCommon",
    "FieldInfo",
    "ImageAsset",
    "InlineObject",
    "LinkInfo",
    "ObjectLookup",
    "ParagraphBorder",
    "ParagraphBorders",
    "RawHint",
    "Run",
    "RunFormat",
    "SmartArt",
    "SmartArtLink",
    "SmartArtNode",
]
