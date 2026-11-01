"""Common annotation vocabulary for bounded chart previews and complete resources."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ...output.xml import append
from .models import ChartLabel, ChartPlotInfo


def append_plots(parent: ET.Element, plots: list[ChartPlotInfo]) -> None:
    for plot in plots:
        if plot.get("unsupported"):
            append(parent, "unsupported", type="chart-plot", source=plot.get("source"), index=plot.get("index"))
            continue
        axes = plot.get("axis_ids", [])
        members = plot.get("series_indices", [])
        append(
            parent,
            "plot",
            index=plot.get("index"),
            type=plot.get("chart_type"),
            grouping=plot.get("grouping"),
            direction=plot.get("direction"),
            axes=" ".join(axes) or None,
            series=" ".join(map(str, members)) or None,
        )


def append_annotations(
    parent: ET.Element,
    labels: list[ChartLabel],
    options: dict[str, str],
    trends: list[dict[str, str]],
) -> None:
    if options:
        append(parent, "label-options", **options)
    for label in labels:
        node = append(
            parent,
            "label",
            label.get("text"),
            index=label.get("index"),
            deleted=True if label.get("deleted") else None,
        )
        if label.get("options"):
            append(node, "label-options", **label["options"])
    for trend in trends:
        append(parent, "trendline", **trend)
