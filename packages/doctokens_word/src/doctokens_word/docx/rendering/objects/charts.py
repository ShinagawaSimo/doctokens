"""Chart inline rendering and resource rendering helpers."""

from __future__ import annotations

from doctokens_core.ooxml.charts.axes import append_chart_axes
from doctokens_core.ooxml.charts.rendering import append_annotations, append_plots
from doctokens_core.output.resources import resource_document
from doctokens_core.output.xml import append, element

from ...model import Chart


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
    combination = chart.get("chartType") == "combination"
    append_chart_axes(node, chart.get("axes", []))
    if combination and chart.get("plots"):
        node.set("plots", ",".join(str(p.get("chart_type", "unknown")) for p in chart["plots"]))
    append_plots(node, chart.get("plots", []))
    for series in chart.get("series") or []:
        child = append(
            node,
            "series",
            index=series.get("index", 0),
            plot=series.get("plotIndex"),
            axes=" ".join(series.get("axis_ids", [])) or None,
            name=series.get("name") or None,
            min=series.get("min"),
            max=series.get("max"),
            type=series.get("chartType") if combination else None,
            hidden=True if series.get("hidden") else None,
        )
        append_annotations(child, series.get("labels", []), series.get("label_options", {}), series.get("trendlines", []))
        arrays = [
            ("category", series.get("categories", [])),
            ("value", series.get("values", [])),
            ("x", series.get("xValues", [])),
            ("y", series.get("yValues", [])),
            ("bubbleSize", series.get("bubbleSizes", [])),
        ]
        for i in range(max((len(values) for _, values in arrays), default=0)):
            append(child, "point", **{name: values[i] for name, values in arrays if i < len(values)})
    return resource_document("docx", node)
