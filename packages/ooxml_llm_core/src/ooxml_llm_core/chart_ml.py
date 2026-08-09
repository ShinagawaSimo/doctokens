"""Shared ChartML (DrawingML Chart) parser.

ChartML is used by DOCX, XLSX, and PPTX for embedded charts.
This module provides format-agnostic extraction of chart metadata
and full cached data series that individual parsers adapt to their models.
"""

from __future__ import annotations

from typing import TypedDict
from xml.etree import ElementTree as ET

NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"

_CHART_TYPE_MAP: dict[str, str] = {
    "areaChart": "area",
    "area3DChart": "area3d",
    "barChart": "bar",
    "bar3DChart": "bar3d",
    "bubbleChart": "bubble",
    "doughnutChart": "doughnut",
    "lineChart": "line",
    "line3DChart": "line3d",
    "ofPieChart": "ofPie",
    "pieChart": "pie",
    "pie3DChart": "pie3d",
    "radarChart": "radar",
    "scatterChart": "scatter",
    "surfaceChart": "surface",
    "surface3DChart": "surface3d",
}

MAX_PREVIEW_POINTS = 8


# ── Output types ──


class ChartPoint(TypedDict, total=False):
    """A single data point with category label and numeric value."""

    category: str
    value: str  # cached string from numCache; may represent float or empty


class ChartSeriesInfo(TypedDict, total=False):
    """Full data for one chart series."""

    index: int
    name: str
    categories: list[str]  # all category labels
    values: list[str]  # all cached values (strings)
    preview: str  # first N points as "cat=val; ..." for inline display
    min: float
    max: float
    formula: str  # cell-range formula from <c:f>


class ChartInfo(TypedDict, total=False):
    """Complete chart metadata and data."""

    chart_type: str
    title: str
    series: list[ChartSeriesInfo]
    series_count: int
    point_count: int


# ── Public entry point ──


def parse_chart_xml(root: ET.Element) -> ChartInfo:
    """Extract chart type, title, and full series data from a ChartML root."""
    plot_area = root.find(f".//{{{NS_C}}}plotArea")
    chart_type = _chart_type(plot_area) or "unknown"
    series = _chart_series(plot_area)
    point_count = sum(len(s.get("categories", [])) for s in series)
    title = _chart_title(root) or ""

    return ChartInfo(
        chart_type=chart_type,
        title=title,
        series=series,
        series_count=len(series),
        point_count=point_count,
    )


# ── Internal helpers ──


def _chart_type(plot_area: ET.Element | None) -> str | None:
    if plot_area is None:
        return None
    for child in plot_area:
        tag = child.tag.split("}", 1)[-1] if "}" in child.tag else child.tag
        if tag in _CHART_TYPE_MAP:
            return _CHART_TYPE_MAP[tag]
    return None


def _chart_title(root: ET.Element) -> str | None:
    title = root.find(f".//{{{NS_C}}}title")
    if title is None:
        # autoTitleDeleted — the chart has no explicit title
        if root.find(f".//{{{NS_C}}}autoTitleDeleted") is not None:
            return None
        return None
    parts = [t.text or "" for t in title.iter(f"{{{NS_A}}}t")]
    text = "".join(parts).strip()
    return text or None


def _chart_series(plot_area: ET.Element | None) -> list[ChartSeriesInfo]:
    if plot_area is None:
        return []

    rows: list[ChartSeriesInfo] = []
    for ser_index, ser in enumerate(plot_area.iter(f"{{{NS_C}}}ser"), start=1):
        categories = _cached_values(_first_child(ser, "cat")) or _cached_values(
            _first_child(ser, "xVal")
        )
        values = _cached_values(_first_child(ser, "val")) or _cached_values(
            _first_child(ser, "yVal")
        )
        name = _series_name(ser)
        point_count = max(len(categories), len(values))

        preview_items: list[str] = []
        for i in range(min(point_count, MAX_PREVIEW_POINTS)):
            cat = categories[i] if i < len(categories) else str(i + 1)
            val = values[i] if i < len(values) else ""
            preview_items.append(f"{cat}={val}" if val else cat)

        row: ChartSeriesInfo = {
            "index": ser_index,
            "categories": categories,
            "values": values,
            "preview": "; ".join(preview_items),
        }
        if name:
            row["name"] = name

        value_numbers: list[float] = []
        for value in values:
            if not value:
                continue
            number = _to_float(value)
            if number is not None:
                value_numbers.append(number)
        if value_numbers:
            row["min"] = min(value_numbers)
            row["max"] = max(value_numbers)

        formula = _first_formula(ser)
        if formula:
            row["formula"] = formula

        rows.append(row)
    return rows


def _first_child(node: ET.Element, local_tag: str) -> ET.Element | None:
    """Find the first direct child with the given local name in NS_C."""
    for child in node:
        tag = child.tag.split("}", 1)[-1] if "}" in child.tag else child.tag
        if tag == local_tag:
            return child
    return None


def _series_name(ser: ET.Element) -> str | None:
    tx = _first_child(ser, "tx")
    if tx is None:
        return None
    values = _cached_values(tx)
    if values:
        return values[0]
    # Fallback: first <c:v> anywhere in tx
    v_elem = tx.find(f".//{{{NS_C}}}v")
    return v_elem.text if v_elem is not None and v_elem.text else None


def _cached_values(node: ET.Element | None) -> list[str]:
    """Read strCache/numCache cached point values."""
    if node is None:
        return []
    points: list[tuple[int, str]] = []
    for pt in node.iter(f"{{{NS_C}}}pt"):
        v_elem = pt.find(f"{{{NS_C}}}v")
        if v_elem is None:
            continue
        idx = int(pt.get("idx") or len(points))
        points.append((idx, v_elem.text or ""))
    return [val for _idx, val in sorted(points, key=lambda item: item[0])]


def _first_formula(node: ET.Element) -> str | None:
    f_elem = node.find(f".//{{{NS_C}}}f")
    return f_elem.text if f_elem is not None and f_elem.text else None


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None
