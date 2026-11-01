"""Spreadsheet drawing objects and chart data."""

from typing import TypedDict

from doctokens_core.ooxml.charts.models import ChartLabel, ChartPlotInfo


class DrawingImage(TypedDict, total=False):
    id: str
    ref: str
    anchorRange: str  # private saved two-cell footprint for range relevance
    alt: str
    part: str
    group: str
    link: str
    href: str
    unparsed: bool


class ChartPoint(TypedDict, total=False):
    category: str
    value: str
    x: str
    y: str
    bubbleSize: str


class DrawingChartSeries(TypedDict, total=False):
    index: int
    pointCount: int
    name: str
    min: float
    max: float
    points: list[ChartPoint]
    plotIndex: int
    chartType: str
    xValues: list[str]
    yValues: list[str]
    bubbleSizes: list[str]
    hidden: bool
    labels: list[ChartLabel]
    label_options: dict[str, str]
    trendlines: list[dict[str, str]]
    axis_ids: list[str]


class DrawingChart(TypedDict, total=False):
    id: str
    ref: str
    anchorRange: str
    type: str
    title: str
    series_count: int
    part: str
    series: list[DrawingChartSeries]
    plots: list[ChartPlotInfo]
    plotTypes: list[str]
    axes: list[dict[str, str]]
    group: str
    unparsed: bool


class DrawingShape(TypedDict, total=False):
    id: str
    ref: str
    anchorRange: str
    kind: str
    name: str
    text: str
    paragraphs: list[str]
    alt: str
    title: str
    group: str
    link: str
    fromShape: str
    toShape: str
    unparsed: bool
