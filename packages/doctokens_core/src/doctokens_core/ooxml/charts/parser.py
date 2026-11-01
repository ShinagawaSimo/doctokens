"""Shared parser for legacy DrawingML charts and Office ChartEx charts.

The three Office parsers deliberately share one chart IR. Chart parts are small
enough to parse eagerly, but their XML is sufficiently different that the
format-specific parsers must not each grow a second implementation. The
``ChartParser`` owns one chart-part traversal and returns compact dictionaries
that can be attached to DOCX, XLSX, or PPTX resources without retaining XML.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from .axes import attach_chart_axes
from .construction import chart_info, series_row
from .models import ChartInfo, ChartPlotInfo, ChartSeriesInfo
from .semantics import axis_ids, series_labels, trendlines
from .values import (
    NS_C,
    NS_CX,
    _chartex_dimension_values,
    _chartex_levels,
    _chartex_series_name,
    _chartex_title,
    _chartml_categories,
    _chartml_series_name,
    _chartml_title,
    _chartml_values,
    _direct_attr,
    _direct_children,
    _first_dimension,
    _first_direct_child,
    _first_formula,
    _flatten_category_levels,
    _local_name,
    _namespace,
    _summary_chart_type,
    _true_value,
    _unique_in_order,
)

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


# ── Output types ──


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
            result = self._parse_chartex(root)
        else:
            result = self._parse_chartml(root)
        attach_chart_axes(result, root)
        return result

    def _parse_chartml(self, root: ET.Element) -> ChartInfo:
        plot_area = root.find(f".//{{{NS_C}}}plotArea")
        plots: list[ChartPlotInfo] = []
        series: list[ChartSeriesInfo] = []
        if plot_area is not None:
            for chart_element in plot_area:
                chart_type = _CHART_TYPE_MAP.get(_local_name(chart_element.tag))
                if chart_type is None:
                    if _local_name(chart_element.tag).endswith("Chart"):
                        plots.append(
                            {"index": len(plots) + 1, "chart_type": "unknown", "unsupported": True, "source": chart_element.tag}
                        )
                    continue
                plot_index = len(plots) + 1
                plot_series = self._parse_chartml_series(chart_element, plot_index, len(series))
                series.extend(plot_series)
                plot: ChartPlotInfo = {
                    "index": plot_index,
                    "chart_type": chart_type,
                }
                if grouping := _direct_attr(chart_element, NS_C, "grouping", "val"):
                    plot["grouping"] = grouping
                if direction := _direct_attr(chart_element, NS_C, "barDir", "val"):
                    plot["direction"] = direction
                if axes := axis_ids(chart_element):
                    plot["axis_ids"] = axes
                plots.append(plot)

        chart_types = _unique_in_order(plot["chart_type"] for plot in plots if not plot.get("unsupported"))
        return chart_info(
            chart_type=_summary_chart_type(chart_types),
            title=_chartml_title(root),
            series=series,
            plots=plots,
        )

    def _parse_chartml_series(
        self,
        chart_element: ET.Element,
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
            values = _chartml_values(value_source)
            x_values = _chartml_values(_first_direct_child(series_element, NS_C, "xVal"))
            y_values = _chartml_values(_first_direct_child(series_element, NS_C, "yVal"))
            bubble_sizes = _chartml_values(_first_direct_child(series_element, NS_C, "bubbleSize"))
            rows.append(
                series_row(
                    index=start_index + offset,
                    plot_index=plot_index,
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
            row = rows[-1]
            inherited_labels, inherited_options = series_labels(chart_element)
            labels, options = series_labels(series_element)
            indexed_labels = {item["index"]: item for item in inherited_labels if "index" in item}
            for label in labels:
                if "index" in label:
                    indexed_labels[label["index"]] = label
            labels = list(indexed_labels.values()) + [item for item in labels if "index" not in item]
            options = {**inherited_options, **options}
            if labels:
                row["labels"] = labels
            if options:
                row["label_options"] = options
            if trends := trendlines(series_element):
                row["trendlines"] = trends
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
                    plot = {"index": len(plots_by_type) + 1, "chart_type": chart_type}
                    plots_by_type[chart_type] = plot
                data_id = _direct_attr(series_element, NS_CX, "dataId", "val")
                data = catalog.get(data_id) if data_id is not None else None
                dimensions = data.numeric_dimensions if data is not None else {}
                values = dimensions.get("val") or dimensions.get("y") or _first_dimension(dimensions)
                row = series_row(
                    index=len(series) + 1,
                    plot_index=plot["index"],
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
                labels, options = series_labels(series_element, chartex=True)
                if labels:
                    row["labels"] = labels
                if options:
                    row["label_options"] = options
                if axes := axis_ids(series_element, chartex=True):
                    row["axis_ids"] = axes
                series.append(row)

        plots = list(plots_by_type.values())
        return chart_info(
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
