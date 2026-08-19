"""Shared parser for legacy DrawingML charts and Office ChartEx charts.

The three Office parsers deliberately share one chart IR. Chart parts are small
enough to parse eagerly, but their XML is sufficiently different that the
format-specific parsers must not each grow a second implementation. The
``ChartParser`` owns one chart-part traversal and returns compact dictionaries
that can be attached to DOCX, XLSX, or PPTX resources without retaining XML.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypedDict
from xml.etree import ElementTree as ET

NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_CX = "http://schemas.microsoft.com/office/drawing/2014/chartex"

CHART_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
CHART_EX_REL_TYPE = "http://schemas.microsoft.com/office/2014/relationships/chartEx"
CHART_RELATIONSHIP_TYPES = frozenset((CHART_REL_TYPE, CHART_EX_REL_TYPE))
CHART_EX_GRAPHIC_DATA_URI = "http://schemas.microsoft.com/office/drawing/2014/chartex"

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
    "stockChart": "stock",
    "surfaceChart": "surface",
    "surface3DChart": "surface3d",
}

MAX_PREVIEW_POINTS = 8


# ── Output types ──


class ChartPoint(TypedDict, total=False):
    """A single data point with category label and numeric value."""

    category: str
    value: str
    x: str
    y: str
    bubble_size: str


class ChartSeriesInfo(TypedDict, total=False):
    """Full data and ownership information for one chart series."""

    index: int
    plot_index: int
    chart_type: str
    name: str
    categories: list[str]
    values: list[str]
    x_values: list[str]
    y_values: list[str]
    bubble_sizes: list[str]
    preview: str
    min: float
    max: float
    formula: str
    category_formula: str
    hidden: bool


class ChartPlotInfo(TypedDict, total=False):
    """One plot family within a chart, including combination-chart ownership."""

    index: int
    chart_type: str
    series_indices: list[int]


class ChartInfo(TypedDict, total=False):
    """Complete format-neutral chart metadata and cached data."""

    chart_type: str
    title: str
    series: list[ChartSeriesInfo]
    series_count: int
    point_count: int
    plots: list[ChartPlotInfo]


@dataclass(slots=True)
class _ChartExData:
    """The dimensions addressed by one ChartEx ``dataId``.

    ChartEx lets a series refer to a shared data block by integer ID. Keeping
    this short-lived catalog makes reference resolution O(series + data), and
    avoids repeatedly scanning ``chartData`` for every series.
    """

    categories: list[str]
    numeric_dimensions: dict[str, list[str]]
    formulas: dict[str, str]


class ChartParser:
    """Parse a legacy ChartML or ChartEx part into the shared chart IR."""

    def parse(self, root: ET.Element) -> ChartInfo:
        if _namespace(root.tag) == NS_CX and _local_name(root.tag) == "chartSpace":
            return self._parse_chartex(root)
        return self._parse_chartml(root)

    def _parse_chartml(self, root: ET.Element) -> ChartInfo:
        plot_area = root.find(f".//{{{NS_C}}}plotArea")
        plots: list[ChartPlotInfo] = []
        series: list[ChartSeriesInfo] = []
        if plot_area is not None:
            for chart_element in plot_area:
                chart_type = _CHART_TYPE_MAP.get(_local_name(chart_element.tag))
                if chart_type is None:
                    continue
                plot_index = len(plots) + 1
                plot_series = self._parse_chartml_series(chart_element, chart_type, plot_index, len(series))
                series.extend(plot_series)
                plot: ChartPlotInfo = {
                    "index": plot_index,
                    "chart_type": chart_type,
                    "series_indices": [item["index"] for item in plot_series],
                }
                plots.append(plot)

        chart_types = _unique_in_order(plot["chart_type"] for plot in plots)
        return _chart_info(
            chart_type=_summary_chart_type(chart_types),
            title=_chartml_title(root),
            series=series,
            plots=plots,
        )

    def _parse_chartml_series(
        self,
        chart_element: ET.Element,
        chart_type: str,
        plot_index: int,
        start_index: int,
    ) -> list[ChartSeriesInfo]:
        rows: list[ChartSeriesInfo] = []
        for offset, series_element in enumerate(_direct_children(chart_element, NS_C, "ser"), start=1):
            category_source = _first_direct_child(series_element, NS_C, "cat")
            if category_source is None:
                category_source = _first_direct_child(series_element, NS_C, "xVal")
            value_source = _first_direct_child(series_element, NS_C, "val")
            if value_source is None:
                value_source = _first_direct_child(series_element, NS_C, "yVal")
            categories = _chartml_categories(category_source)
            values = _cached_values_from(value_source)
            x_values = _cached_values_from(_first_direct_child(series_element, NS_C, "xVal"))
            y_values = _cached_values_from(_first_direct_child(series_element, NS_C, "yVal"))
            bubble_sizes = _cached_values_from(_first_direct_child(series_element, NS_C, "bubbleSize"))
            rows.append(
                _series_row(
                    index=start_index + offset,
                    plot_index=plot_index,
                    chart_type=chart_type,
                    categories=categories,
                    values=values,
                    x_values=x_values,
                    y_values=y_values,
                    bubble_sizes=bubble_sizes,
                    name=_chartml_series_name(series_element),
                    formula=_first_formula(value_source),
                    category_formula=_first_formula(category_source),
                    hidden=False,
                )
            )
        return rows

    def _parse_chartex(self, root: ET.Element) -> ChartInfo:
        catalog = self._build_chartex_data_catalog(root)
        chart = _first_direct_child(root, NS_CX, "chart")
        plot_area = _first_direct_child(chart, NS_CX, "plotArea") if chart is not None else None
        region = _first_direct_child(plot_area, NS_CX, "plotAreaRegion") if plot_area is not None else None
        series: list[ChartSeriesInfo] = []
        plots_by_type: dict[str, ChartPlotInfo] = {}
        if region is not None:
            for series_element in _direct_children(region, NS_CX, "series"):
                chart_type = series_element.get("layoutId") or "unknown"
                plot = plots_by_type.get(chart_type)
                if plot is None:
                    plot = {"index": len(plots_by_type) + 1, "chart_type": chart_type, "series_indices": []}
                    plots_by_type[chart_type] = plot
                data_id = _direct_attr(series_element, NS_CX, "dataId", "val")
                data = catalog.get(data_id) if data_id is not None else None
                dimensions = data.numeric_dimensions if data is not None else {}
                values = dimensions.get("val") or dimensions.get("y") or _first_dimension(dimensions)
                row = _series_row(
                    index=len(series) + 1,
                    plot_index=plot["index"],
                    chart_type=chart_type,
                    categories=data.categories if data is not None else [],
                    values=values,
                    x_values=dimensions.get("x", []),
                    y_values=dimensions.get("y", []),
                    bubble_sizes=dimensions.get("size", []),
                    name=_chartex_series_name(series_element),
                    formula=(data.formulas.get("val") or data.formulas.get("y")) if data is not None else None,
                    category_formula=data.formulas.get("cat") if data is not None else None,
                    hidden=_true_value(series_element.get("hidden")),
                )
                series.append(row)
                plot["series_indices"].append(row["index"])

        plots = list(plots_by_type.values())
        return _chart_info(
            chart_type=_summary_chart_type([plot["chart_type"] for plot in plots]),
            title=_chartex_title(chart),
            series=series,
            plots=plots,
        )

    def _build_chartex_data_catalog(self, root: ET.Element) -> dict[str, _ChartExData]:
        chart_data = _first_direct_child(root, NS_CX, "chartData")
        if chart_data is None:
            return {}
        catalog: dict[str, _ChartExData] = {}
        for data in _direct_children(chart_data, NS_CX, "data"):
            data_id = data.get("id")
            if data_id is None:
                continue
            categories: list[str] = []
            dimensions: dict[str, list[str]] = {}
            formulas: dict[str, str] = {}
            for dimension in data:
                if _namespace(dimension.tag) != NS_CX:
                    continue
                local = _local_name(dimension.tag)
                dimension_type = dimension.get("type")
                if local == "strDim" and dimension_type == "cat":
                    categories = _flatten_category_levels(_chartex_levels(dimension))
                    formula = _first_formula(dimension, namespace=NS_CX)
                    if formula:
                        formulas["cat"] = formula
                elif local == "numDim" and dimension_type:
                    dimensions[dimension_type] = _chartex_dimension_values(dimension)
                    formula = _first_formula(dimension, namespace=NS_CX)
                    if formula:
                        formulas[dimension_type] = formula
            catalog[data_id] = _ChartExData(categories, dimensions, formulas)
        return catalog


def parse_chart_xml(root: ET.Element) -> ChartInfo:
    """Compatibility entry point for callers that do not need parser state."""
    return ChartParser().parse(root)


# ── IR construction ──


def _chart_info(
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
        "point_count": sum(_series_point_count(item) for item in series),
    }
    if chart_type == "combination":
        result["plots"] = plots
    else:
        for series_item in series:
            series_item.pop("plot_index", None)
            series_item.pop("chart_type", None)
    if title:
        result["title"] = title
    return result


def _series_row(
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


# ── Legacy ChartML ──


def _chartml_title(root: ET.Element) -> str | None:
    return _drawing_text(_first_descendant(root, NS_C, "title"))


def _chartml_series_name(series_element: ET.Element) -> str | None:
    text = _first_direct_child(series_element, NS_C, "tx")
    return _drawing_text(text) or _first_value(text)


def _chartml_categories(node: ET.Element | None) -> list[str]:
    if node is None:
        return []
    multi_level = _first_descendant(node, NS_C, "multiLvlStrCache")
    if multi_level is not None:
        levels = [_indexed_point_values(level, NS_C) for level in _direct_children(multi_level, NS_C, "lvl")]
        return _flatten_category_levels(levels)
    values = _cached_values_from(node)
    return values


def _cached_values_from(node: ET.Element | None) -> list[str]:
    if node is None:
        return []
    cache = _first_descendant(node, NS_C, "numCache")
    if cache is None:
        cache = _first_descendant(node, NS_C, "strCache")
    return _indexed_point_values(cache, NS_C) if cache is not None else []


# ── ChartEx ──


def _chartex_title(chart: ET.Element | None) -> str | None:
    return _drawing_text(_first_direct_child(chart, NS_CX, "title")) if chart is not None else None


def _chartex_series_name(series_element: ET.Element) -> str | None:
    text = _first_direct_child(series_element, NS_CX, "tx")
    return _drawing_text(text) or _first_value(text)


def _chartex_levels(dimension: ET.Element) -> list[list[str]]:
    return [_indexed_point_values(level, NS_CX) for level in _direct_children(dimension, NS_CX, "lvl")]


def _chartex_dimension_values(dimension: ET.Element) -> list[str]:
    levels = _chartex_levels(dimension)
    return levels[-1] if levels else []


# ── XML helpers ──


def _namespace(tag: str) -> str | None:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _direct_children(node: ET.Element | None, namespace: str, local_name: str) -> list[ET.Element]:
    if node is None:
        return []
    return [child for child in node if child.tag == f"{{{namespace}}}{local_name}"]


def _first_direct_child(node: ET.Element | None, namespace: str, local_name: str) -> ET.Element | None:
    return node.find(f"{{{namespace}}}{local_name}") if node is not None else None


def _first_descendant(node: ET.Element | None, namespace: str, local_name: str) -> ET.Element | None:
    return node.find(f".//{{{namespace}}}{local_name}") if node is not None else None


def _direct_attr(node: ET.Element | None, namespace: str, local_name: str, attribute: str) -> str | None:
    child = _first_direct_child(node, namespace, local_name)
    return child.get(attribute) if child is not None else None


def _indexed_point_values(node: ET.Element, namespace: str) -> list[str]:
    points: dict[int, str] = {}
    for fallback_index, point in enumerate(_direct_children(node, namespace, "pt")):
        index = _safe_int(point.get("idx"))
        points[index if index is not None else fallback_index] = point.text or _first_value(point) or ""
    if not points:
        return []
    return [points.get(index, "") for index in range(max(points) + 1)]


def _first_formula(node: ET.Element | None, *, namespace: str = NS_C) -> str | None:
    formula = _first_descendant(node, namespace, "f")
    return formula.text if formula is not None and formula.text else None


def _first_value(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    for element in node.iter():
        if _local_name(element.tag) == "v" and element.text:
            return element.text
    return None


def _drawing_text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    text = "".join(element.text or "" for element in node.iter(f"{{{NS_A}}}t")).strip()
    return text or None


def _flatten_category_levels(levels: list[list[str]]) -> list[str]:
    if not levels:
        return []
    length = max(len(level) for level in levels)
    return [" / ".join(level[index] for level in levels if index < len(level) and level[index]) for index in range(length)]


def _summary_chart_type(chart_types: list[str]) -> str:
    unique = _unique_in_order(chart_types)
    if not unique:
        return "unknown"
    return unique[0] if len(unique) == 1 else "combination"


def _unique_in_order(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _first_dimension(dimensions: dict[str, list[str]]) -> list[str]:
    return next(iter(dimensions.values()), [])


def _series_point_count(series: ChartSeriesInfo) -> int:
    return max(
        len(series.get("categories", [])),
        len(series.get("values", [])),
        len(series.get("x_values", [])),
        len(series.get("y_values", [])),
        len(series.get("bubble_sizes", [])),
    )


def _safe_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _true_value(value: str | None) -> bool:
    return value in {"1", "true", "True"}
