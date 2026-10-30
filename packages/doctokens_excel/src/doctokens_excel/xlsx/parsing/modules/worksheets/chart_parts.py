"""Adapt shared ChartML data to XLSX drawing chart records."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.contracts.models import ParseWarning
from doctokens_core.ooxml.charts.parser import ChartParser

from ....model.drawing import ChartPoint, DrawingChart, DrawingChartSeries
from .post_common import _warn


def parse_chart_part(pkg: PackageReader, chart_part: str, warnings: list[ParseWarning] | None = None) -> DrawingChart:
    """Parse a chart XML part via shared ChartML parser; return structured dict."""
    if not chart_part or not pkg.exists(chart_part):
        _warn(warnings, "CHART_PART_MISSING", "Referenced chart part is missing", chart_part)
        return {"type": "", "title": "", "series_count": 0, "unparsed": True}
    try:
        root = pkg.read_xml(chart_part)
        chart_info = ChartParser().parse(root)
    except (ET.ParseError, ValueError, KeyError) as exc:
        _warn(warnings, "CHART_XML_INVALID", f"Invalid chart XML: {exc}", chart_part)
        return {"type": "", "title": "", "series_count": 0, "unparsed": True}

    series_list: list[DrawingChartSeries] = []
    for source_series in chart_info.get("series", []):
        point_count = max(
            len(source_series.get("categories", [])),
            len(source_series.get("values", [])),
            len(source_series.get("x_values", [])),
            len(source_series.get("y_values", [])),
            len(source_series.get("bubble_sizes", [])),
        )
        series_item: DrawingChartSeries = {
            "index": source_series["index"],
            "pointCount": point_count,
        }
        if source_series.get("name"):
            series_item["name"] = source_series["name"]
        if "min" in source_series:
            series_item["min"] = source_series["min"]
        if "max" in source_series:
            series_item["max"] = source_series["max"]
        if "plot_index" in source_series:
            series_item["plotIndex"] = source_series["plot_index"]
        if "chart_type" in source_series:
            series_item["chartType"] = source_series["chart_type"]
        if source_series.get("x_values"):
            series_item["xValues"] = source_series["x_values"]
        if source_series.get("y_values"):
            series_item["yValues"] = source_series["y_values"]
        if source_series.get("bubble_sizes"):
            series_item["bubbleSizes"] = source_series["bubble_sizes"]
        if source_series.get("hidden"):
            series_item["hidden"] = True
        for key in ("labels", "label_options", "trendlines", "axis_ids"):
            if key in source_series:
                series_item[key] = source_series[key]
        # Full data points
        categories = source_series.get("categories", [])
        values = source_series.get("values", [])
        x_values = source_series.get("x_values", [])
        y_values = source_series.get("y_values", [])
        bubble_sizes = source_series.get("bubble_sizes", [])
        points: list[ChartPoint] = []
        for index in range(point_count):
            point: ChartPoint = {}
            if index < len(categories):
                point["category"] = categories[index]
            if index < len(values):
                point["value"] = values[index]
            if index < len(x_values):
                point["x"] = x_values[index]
            if index < len(y_values):
                point["y"] = y_values[index]
            if index < len(bubble_sizes):
                point["bubbleSize"] = bubble_sizes[index]
            if point:
                points.append(point)
        if points:
            series_item["points"] = points
        series_list.append(series_item)

    result: DrawingChart = {
        "type": chart_info.get("chart_type", ""),
        "title": chart_info.get("title", ""),
        "series_count": chart_info.get("series_count", 0),
        "series": series_list,
    }
    if result["type"] in {"", "unknown"}:
        result["unparsed"] = True
        _warn(warnings, "CHART_TYPE_UNSUPPORTED", "Saved chart has no supported readable chart type", chart_part)
    if chart_info.get("plots"):
        result["plots"] = chart_info["plots"]
    if chart_info.get("axes"):
        result["axes"] = chart_info["axes"]
    plot_types = [plot.get("chart_type", "unknown") for plot in chart_info.get("plots", [])]
    if chart_info.get("chart_type") == "combination" and plot_types:
        result["plotTypes"] = plot_types
    return result
