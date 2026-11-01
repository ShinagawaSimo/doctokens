"""Construct shared saved-data chart records independently of XML traversal."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from .models import ChartInfo, ChartPlotInfo, ChartPoint, ChartSeriesInfo


def chart_info(
    *,
    chart_type: str,
    title: str | None,
    series: list[ChartSeriesInfo],
    plots: list[ChartPlotInfo],
) -> ChartInfo:
    kinds = {plot["index"]: plot["chart_type"] for plot in plots}
    for item in series:
        if kinds.get(item.get("plot_index", -1)) in {"scatter", "bubble"}:
            item.pop("categories", None)
            item.pop("values", None)
    result: ChartInfo = {
        "chart_type": chart_type,
        "series": series,
        "series_count": len(series),
        "point_count": sum(series_point_count(item) for item in series),
    }
    if chart_type == "combination" or any(
        plot.get("grouping") or plot.get("axis_ids") or plot.get("unsupported") for plot in plots
    ):
        result["plots"] = plots
    else:
        for series_item in series:
            series_item.pop("plot_index", None)
    if title:
        result["title"] = title
    return result


def series_row(
    *,
    index: int,
    plot_index: int,
    categories: list[str],
    values: list[str],
    x_values: list[str],
    y_values: list[str],
    bubble_sizes: list[str],
    name: str | None,
    formula: str | None,
    category_formula: str | None,
    hidden: bool,
) -> ChartSeriesInfo:
    row: ChartSeriesInfo = {
        "index": index,
        "plot_index": plot_index,
        "categories": categories,
        "values": values,
    }
    if x_values:
        row["x_values"] = x_values
    if y_values:
        row["y_values"] = y_values
    if bubble_sizes:
        row["bubble_sizes"] = bubble_sizes
    if name:
        row["name"] = name
    if formula:
        row["formula"] = formula
    if category_formula:
        row["category_formula"] = category_formula
    if hidden:
        row["hidden"] = True
    return row


def series_point_count(series: ChartSeriesInfo) -> int:
    return max(len(values) for _, values in series_arrays(series))


def series_arrays(series: ChartSeriesInfo) -> tuple[tuple[str, list[str]], ...]:
    return (
        ("category", series.get("categories", [])),
        ("value", series.get("values", [])),
        ("x", series.get("x_values", [])),
        ("y", series.get("y_values", [])),
        ("bubble_size", series.get("bubble_sizes", [])),
    )


def iter_series_points(series: ChartSeriesInfo) -> Iterator[ChartPoint]:
    """Keep saved cache positions, including holes, without numeric conversion."""
    arrays = series_arrays(series)
    for index in range(series_point_count(series)):
        yield cast(ChartPoint, {key: values[index] for key, values in arrays if index < len(values)})
