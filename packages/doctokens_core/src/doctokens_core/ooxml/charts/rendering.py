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
            axes=" ".join(str(value) for value in axes) if isinstance(axes, list) and axes else None,
            series=" ".join(str(value) for value in members) if isinstance(members, list) and members else None,
        )


def append_annotations(
    parent: ET.Element,
    labels: list[ChartLabel],
    options: dict[str, str],
    trends: list[dict[str, str]],
    *,
    preview: bool = False,
) -> None:
    if options:
        append(parent, "label-options", **options)
    shown = 0
    for label in labels:
        if preview and ("index" not in label or label["index"] >= 8):
            continue
        if preview and shown >= 8:
            break
        shown += 1
        node = append(
            parent,
            "label",
            label.get("text"),
            index=label.get("index"),
            position=label.get("position"),
            deleted=True if label.get("deleted") else None,
        )
        if label.get("options"):
            append(node, "label-options", **label["options"])
        if label.get("unsupported"):
            append(node, "unsupported", type="chart-label")
    for trend in trends[:8] if preview else trends:
        append(parent, "trendline", **trend)
