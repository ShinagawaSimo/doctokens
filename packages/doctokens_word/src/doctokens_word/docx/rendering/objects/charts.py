"""Chart inline rendering and resource rendering helpers."""

from __future__ import annotations

from doctokens_core.ooxml.charts.axes import append_chart_axes
from doctokens_core.ooxml.charts.construction import iter_series_points
from doctokens_core.ooxml.charts.models import ChartInfo, ChartSeriesInfo
from doctokens_core.ooxml.charts.rendering import append_annotations, append_plots, append_points
from doctokens_core.output.resources import resource_document
from doctokens_core.output.xml import append, element

from ...model import Chart, InlineObject


def reading_info(chart: Chart | InlineObject) -> ChartInfo:
    series: list[ChartSeriesInfo] = []
    for item in chart.get("series", []):
        row: ChartSeriesInfo = {"index": item["index"], "point_count": item.get("pointCount", 0)}
        for old, new in (
            ("name", "name"),
            ("categories", "categories"),
            ("values", "values"),
            ("xValues", "x_values"),
            ("yValues", "y_values"),
            ("bubbleSizes", "bubble_sizes"),
            ("plotIndex", "plot_index"),
            ("hidden", "hidden"),
            ("axis_ids", "axis_ids"),
            ("labels", "labels"),
            ("label_options", "label_options"),
            ("trendlines", "trendlines"),
        ):
            if old in item:
                row[new] = item[old]  # type: ignore[literal-required]
        series.append(row)
    return {
        "series": series,
        "series_count": chart.get("seriesCount", len(series)),
        "point_count": chart.get("pointCount", max((item.get("point_count", 0) for item in series), default=0)),
        "axes": chart.get("axes", []),
        "plots": chart.get("plots", []),
    }


def render_chart_resource(chart: Chart) -> str:
    """Render full chart data directly as a complete DTX resource document."""
    node = element(
        "chart",
        id=chart.get("id", "?"),
        type=chart.get("chartType", "?"),
        title=chart.get("title") or None,
        series=chart.get("seriesCount", 0),
        points=chart.get("pointCount", 0),
    )
    append_chart_axes(node, chart.get("axes", []))
    append_plots(node, chart.get("plots", []))
    for series in reading_info(chart)["series"]:
        child = append(
            node,
            "series",
            index=series.get("index", 0),
            plot=series.get("plot_index"),
            axes=" ".join(series.get("axis_ids", [])) or None,
            name=series.get("name") or None,
            hidden=True if series.get("hidden") else None,
        )
        append_annotations(child, series.get("labels", []), series.get("label_options", {}), series.get("trendlines", []))
        append_points(child, iter_series_points(series))
    return resource_document("docx", node)
