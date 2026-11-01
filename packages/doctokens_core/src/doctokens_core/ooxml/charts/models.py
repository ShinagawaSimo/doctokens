"""Shared saved-data chart records, independent of parsing and serialization."""

from __future__ import annotations

from typing import TypedDict


class ChartPoint(TypedDict, total=False):
    """A single data point with category label and numeric value."""

    category: str
    value: str
    x: str
    y: str
    bubble_size: str


class ChartSeriesInfo(TypedDict, total=False):
    """Full data and ownership information for one chart series."""

    index: int
    point_count: int
    plot_index: int
    chart_type: str
    name: str
    categories: list[str]
    values: list[str]
    x_values: list[str]
    y_values: list[str]
    bubble_sizes: list[str]
    preview: str
    min: float
    max: float
    formula: str
    category_formula: str
    hidden: bool
    labels: list[ChartLabel]
    label_options: dict[str, str]
    trendlines: list[dict[str, str]]
    axis_ids: list[str]


class ChartPlotInfo(TypedDict, total=False):
    """One plot family within a chart, including combination-chart ownership."""

    index: int
    chart_type: str
    series_indices: list[int]
    grouping: str
    direction: str
    axis_ids: list[str]
    unsupported: bool
    source: str


class ChartLabel(TypedDict, total=False):
    index: int
    text: str
    deleted: bool
    options: dict[str, str]


class ChartInfo(TypedDict, total=False):
    """Complete format-neutral chart metadata and cached data."""

    chart_type: str
    title: str
    series: list[ChartSeriesInfo]
    series_count: int
    point_count: int
    plots: list[ChartPlotInfo]
    axes: list[dict[str, str]]
