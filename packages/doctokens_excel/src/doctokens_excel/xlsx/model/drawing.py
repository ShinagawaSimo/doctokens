"""Spreadsheet drawing objects and chart data."""

from typing import TypedDict


class DrawingImage(TypedDict, total=False):
    id: str
    ref: str
    alt: str
    part: str
    title: str
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


class DrawingChart(TypedDict, total=False):
    id: str
    ref: str
    type: str
    title: str
    series_count: int
    part: str
    series: list[DrawingChartSeries]
    plotTypes: list[str]
    axes: list[dict[str, str]]
    group: str
    unparsed: bool


class DrawingShape(TypedDict, total=False):
    id: str
    ref: str
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
