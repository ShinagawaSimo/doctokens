"""Bounded reading projection; complete resource serializers do not use it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from xml.etree import ElementTree as ET

from ...output.xml import append
from .models import ChartInfo, ChartPoint, ChartSeriesInfo
from .rendering import append_annotations

_AXIS_FIELDS = {
    "id",
    "kind",
    "cross_axis",
    "title",
    "num_format",
    "minimum",
    "maximum",
    "log_base",
    "orientation",
    "display_unit",
    "custom_unit",
}


def _arrays(series: ChartSeriesInfo) -> tuple[tuple[str, list[str]], ...]:
    return (
        ("category", series.get("categories", [])),
        ("value", series.get("values", [])),
        ("x", series.get("x_values", [])),
        ("y", series.get("y_values", [])),
        ("bubble_size", series.get("bubble_sizes", [])),
    )


@dataclass
class _Budget:
    remaining: int = 2400
    changes: int = 0
    annotations: int = 16

    def value(self, value: object, *, label: bool = False) -> str | None:
        text = str(value)
        limit = min(160, self.remaining)
        if len(text) > limit:
            self.changes += 1
            if not label or not limit:
                return None
            text = text[: limit - 1] + "…"
        self.remaining -= len(text)
        return text

    def attrs(self, values: dict[str, object]) -> dict[str, object]:
        result: dict[str, object] = {}
        for index, (key, value) in enumerate(values.items()):
            if value is None or value == "":
                continue
            if index >= 16:
                self.changes += 1
                break
            normalized = self.value(value, label=key in {"title", "name", "category", "text"})
            if normalized is not None:
                result[key] = normalized
        return result


def series_points(series: ChartSeriesInfo) -> int:
    return max(series.get("point_count", 0), len(series.get("points", [])), *(len(values) for _, values in _arrays(series)))


def append_chart_preview(parent: ET.Element, chart: ChartInfo) -> None:
    """Use at most 8 series, 8 points each, 8 axes/plots and 16 annotations."""
    budget = _Budget()
    series = chart.get("series", [])
    parent.set("series", str(chart.get("series_count", len(series))))
    parent.set("points", str(chart.get("point_count", sum(series_points(item) for item in series))))
    for key in ("title", "name"):
        if key in parent.attrib:
            original = parent.attrib.pop(key)
            value = budget.value(original, label=True)
            if value:
                parent.set(key, value)
    shown = series[:8]
    shown_ids = {item.get("index", index) for index, item in enumerate(shown)}
    axes = chart.get("axes", [])
    retained_axes = axes[:8]
    axis_ids = {axis["id"] for axis in retained_axes if "id" in axis}
    if len(series) > 8 or len(axes) > 8 or chart.get("series_count", len(series)) > len(shown):
        budget.changes += 1
    for axis in retained_axes:
        attrs: dict[str, object] = {key: value for key, value in axis.items() if key in _AXIS_FIELDS}
        if attrs.get("cross_axis") not in axis_ids and attrs.pop("cross_axis", None) is not None:
            budget.changes += 1
        identity = attrs.pop("id", None)
        append(parent, "axis", id=identity, **budget.attrs(attrs))
    plots = chart.get("plots", [])
    retained_plots: set[int] = set()
    for ordinal, plot in enumerate(plots[:8]):
        members = plot.get("series_indices", [])
        included = [member for member in members if member in shown_ids][:8]
        if members and not included:
            budget.changes += 1
            continue
        index = plot.get("index", ordinal)
        retained_plots.add(index)
        if plot.get("unsupported"):
            append(parent, "unsupported", type="chart-plot", index=index)
            continue
        attrs = {
            "type": plot.get("chart_type"),
            "grouping": plot.get("grouping"),
            "direction": plot.get("direction"),
            "series": " ".join(map(str, included)) or None,
            "axes": _axis_refs(plot.get("axis_ids", []), axis_ids, budget),
        }
        if len(included) != len(members):
            budget.changes += 1
        append(parent, "plot", index=index, **budget.attrs(attrs))
    if len(plots) > 8:
        budget.changes += 1
    for ordinal, item in enumerate(shown):
        before = budget.changes
        plot_id = item.get("plot_index")
        if plot_id is not None and plot_id not in retained_plots:
            budget.changes += 1
        node = append(
            parent,
            "series",
            index=item.get("index", ordinal),
            name=budget.value(item["name"], label=True) if item.get("name") else None,
            plot=plot_id if plot_id in retained_plots else None,
            axes=_axis_refs(item.get("axis_ids", []), axis_ids, budget),
            hidden=True if item.get("hidden") else None,
        )
        count = series_points(item)
        if count > 8:
            budget.changes += 1
        visible_points: set[int] = set()
        for index in range(min(8, count)):
            point = _point(item, index)
            old_remaining, old_changes = budget.remaining, budget.changes
            attrs = budget.attrs({"bubbleSize" if key == "bubble_size" else key: value for key, value in point.items()})
            # Numeric data is indivisible: never publish a clipped numeric prefix.
            if any(point.get(key) not in (None, "") and key not in attrs for key in ("value", "x", "y")) or (
                point.get("bubble_size") not in (None, "") and "bubbleSize" not in attrs
            ):
                budget.remaining = old_remaining
                budget.changes += 1
                continue
            append(node, "point", index=index, **attrs, truncated=True if budget.changes != old_changes else None)
            visible_points.add(index)
        _annotations(node, item, budget, visible_points)
        if budget.changes != before:
            node.set("truncated", "true")
    if budget.changes:
        parent.set("truncated", "true")
    parent.attrib = dict(sorted(parent.attrib.items()))


def _axis_refs(values: list[str], known: set[str], budget: _Budget) -> str | None:
    retained = [value for value in values[:8] if value in known]
    if len(retained) != len(values):
        budget.changes += 1
    return " ".join(retained) or None


def _point(series: ChartSeriesInfo, index: int) -> ChartPoint:
    if "points" in series:
        return series["points"][index] if index < len(series["points"]) else {}
    return cast(ChartPoint, {key: values[index] for key, values in _arrays(series) if index < len(values)})


def _annotations(parent: ET.Element, series: ChartSeriesInfo, budget: _Budget, visible_points: set[int]) -> None:
    labels, trends = series.get("labels", []), series.get("trendlines", [])
    temporary = ET.Element("annotations")
    append_annotations(
        temporary,
        [label for label in labels if label.get("index") in visible_points],
        series.get("label_options", {}),
        trends,
        preview=True,
    )
    if len(labels) != sum(1 for child in temporary if child.tag == "label") or len(trends) > 8:
        budget.changes += 1

    def copy(source: ET.Element, target: ET.Element) -> None:
        if not budget.annotations:
            budget.changes += 1
            return
        budget.annotations -= 1
        node = append(
            target,
            source.tag,
            budget.value(source.text, label=True) if source.text else None,
            **budget.attrs(dict(source.attrib)),
        )
        for child in source:
            copy(child, node)

    for child in temporary:
        copy(child, parent)


def plain_chart(resource_id: str | None, kind: str, title: str | None, names: list[str], count: int) -> str:
    budget = _Budget(remaining=512)
    title_text = budget.value(title, label=True) if title else None
    labels = [value for name in names[:8] if (value := budget.value(name, label=True))]
    label = f"Chart{' ' + resource_id if resource_id else ''}"
    if title_text:
        label += f": {title_text}"
    label += f" ({kind}, {count} series)"
    if labels:
        label += "; " + ", ".join(labels)
    if len(names) > 8 or budget.changes:
        label += "; truncated"
    return f"[{label}]"
