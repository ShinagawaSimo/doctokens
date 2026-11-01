"""Common annotation vocabulary for bounded chart previews and complete resources."""

from __future__ import annotations

from collections.abc import Iterable
from xml.etree import ElementTree as ET

from ...output.xml import append
from .models import ChartLabel, ChartPlotInfo, ChartPoint


def append_plots(parent: ET.Element, plots: list[ChartPlotInfo]) -> None:
    for plot in plots:
        if plot.get("unsupported"):
            append(parent, "unsupported", type="chart-plot", source=plot.get("source"), index=plot.get("index"))
            continue
        axes = plot.get("axis_ids", [])
        append(
            parent,
            "plot",
            index=plot.get("index"),
            type=plot.get("chart_type") if plot.get("chart_type") != parent.get("type") else None,
            grouping=plot.get("grouping"),
            direction=plot.get("direction"),
            axes=" ".join(axes) or None,
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


def append_points(parent: ET.Element, points: Iterable[ChartPoint]) -> None:
    """One complete saved-data representation shared by all resource writers."""
    for index, point in enumerate(points):
        append(
            parent,
            "point",
            index=index,
            **{"bubbleSize" if key == "bubble_size" else key: value for key, value in point.items() if value != ""},
        )
