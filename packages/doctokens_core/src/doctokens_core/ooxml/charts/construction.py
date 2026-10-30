"""Construct shared saved-data chart records independently of XML traversal."""

from __future__ import annotations

from .models import ChartInfo, ChartPlotInfo, ChartSeriesInfo
from .values import _to_float

MAX_PREVIEW_POINTS = 8


def chart_info(
    *,
    chart_type: str,
    title: str | None,
    series: list[ChartSeriesInfo],
    plots: list[ChartPlotInfo],
) -> ChartInfo:
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
            series_item.pop("chart_type", None)
    if title:
        result["title"] = title
    return result


def series_row(
    *,
    index: int,
    plot_index: int,
    chart_type: str,
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
    point_count = max(len(categories), len(values), len(x_values), len(y_values), len(bubble_sizes))
    preview_items: list[str] = []
    for item_index in range(min(point_count, MAX_PREVIEW_POINTS)):
        category = categories[item_index] if item_index < len(categories) else str(item_index + 1)
        value = values[item_index] if item_index < len(values) else ""
        preview_items.append(f"{category}={value}" if value else category)
    row: ChartSeriesInfo = {
        "index": index,
        "plot_index": plot_index,
        "chart_type": chart_type,
        "categories": categories,
        "values": values,
        "preview": "; ".join(preview_items),
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
    numbers = [number for value in values if (number := _to_float(value)) is not None]
    if numbers:
        row["min"] = min(numbers)
        row["max"] = max(numbers)
    return row


def series_point_count(series: ChartSeriesInfo) -> int:
    return max(
        len(series.get("categories", [])),
        len(series.get("values", [])),
        len(series.get("x_values", [])),
        len(series.get("y_values", [])),
        len(series.get("bubble_sizes", [])),
    )
