"""Bounded saved-data chart previews; full series stay in the resource API."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.ooxml.charts.axes import append_chart_axes
from doctokens_core.ooxml.charts.rendering import append_annotations, append_plots
from doctokens_core.output.xml import append

from ..model.presentation import ChartRecord


def append_chart_preview(parent: ET.Element, chart: ChartRecord) -> None:
    append_chart_axes(parent, chart.get("axes", []))
    append_plots(parent, chart.get("plots", []))
    for ordinal, series in enumerate(chart.get("series", [])[:8]):
        child = append(
            parent,
            "series",
            index=series.get("index", ordinal),
            name=series.get("name"),
            plot=series.get("plot_index"),
            axes=" ".join(series.get("axis_ids", [])) or None,
        )
        append_annotations(
            child, series.get("labels", []), series.get("label_options", {}), series.get("trendlines", []), preview=True
        )
        arrays = [
            ("category", series.get("categories", [])),
            ("value", series.get("values", [])),
            ("x", series.get("x_values", [])),
            ("y", series.get("y_values", [])),
            ("bubbleSize", series.get("bubble_sizes", [])),
        ]
        for index in range(min(8, max((len(values) for _, values in arrays), default=0))):
            append(child, "point", index=index, **{key: values[index] for key, values in arrays if index < len(values)})
