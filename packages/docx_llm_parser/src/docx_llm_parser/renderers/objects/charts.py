"""Chart inline rendering and resource rendering helpers."""

from __future__ import annotations

from html import escape as escape_text

from ...core.models import Chart, ChartSeries, InlineObject
from ..common import constants as _constants


def chart_to_output(chart: InlineObject) -> str:
    """Render an inline chart summary; full points are available through get_resource."""
    attrs = _chart_attrs(chart)
    type_attrs = chart_type_attrs(chart, chart.get("chartType", "?"))
    if type_attrs:
        attrs += type_attrs
    return f"<chart {attrs} truncated>\n"


def chart_type_attrs(chart: InlineObject, chart_type: str) -> str:
    """Return attributes that make each chart family easier to skim."""
    series = chart.get("series") or []
    if chart_type in ("bar", "bar3d", "line", "line3d", "area", "area3d", "radar"):
        return _bar_like_chart_attrs(series)
    if chart_type in ("pie", "pie3d", "doughnut"):
        return _pie_chart_attrs(series)
    if chart_type in ("scatter", "bubble"):
        return _scatter_chart_attrs(chart, series)
    if chart_type == "stock":
        return _stock_chart_attrs(series)
    if chart_type in ("surface", "surface3d"):
        return _surface_chart_attrs(series)
    return ""


def render_chart_resource(chart: Chart) -> str:
    """Render a chart resource with its full series data."""
    output_parts = [f"<chart {_chart_attrs(chart, include_points=True)}>"]
    is_combination = chart.get("chartType") == "combination"

    if is_combination:
        for plot in chart.get("plots") or []:
            plot_attrs = f"index={plot.get('index', 0)} type={escape_text(plot.get('chartType', 'unknown'), quote=True)}"
            series_indices = plot.get("seriesIndices", [])
            if series_indices:
                plot_attrs += f" series={','.join(str(index) for index in series_indices)}"
            output_parts.append(f"\n<plot {plot_attrs}/>")

    for series in chart.get("series") or []:
        series_attrs = f"index={series.get('index', 0)}"
        if series.get("name"):
            series_attrs += f" name={escape_text(series['name'], quote=True)}"
        if "min" in series:
            series_attrs += f" min={series['min']}"
        if "max" in series:
            series_attrs += f" max={series['max']}"
        if is_combination and series.get("chartType"):
            series_attrs += f" type={escape_text(series['chartType'], quote=True)}"
        if series.get("hidden"):
            series_attrs += " hidden"
        output_parts.append(f"\n<series {series_attrs}>")

        categories = series.get("categories", [])
        values = series.get("values", [])
        x_values = series.get("xValues", [])
        y_values = series.get("yValues", [])
        bubble_sizes = series.get("bubbleSizes", [])
        for index in range(max(len(categories), len(values), len(x_values), len(y_values), len(bubble_sizes))):
            point_attrs = ""
            if index < len(categories):
                point_attrs += f" category={escape_text(categories[index], quote=True)}"
            if index < len(values):
                point_attrs += f" value={escape_text(values[index], quote=True)}"
            if index < len(x_values):
                point_attrs += f" x={escape_text(x_values[index], quote=True)}"
            if index < len(y_values):
                point_attrs += f" y={escape_text(y_values[index], quote=True)}"
            if index < len(bubble_sizes):
                point_attrs += f" bubbleSize={escape_text(bubble_sizes[index], quote=True)}"
            output_parts.append(f"\n<point{point_attrs}/>")

    return "".join(output_parts)


def _chart_attrs(chart: Chart | InlineObject, *, include_points: bool = False) -> str:
    attrs = f"id={chart.get('id', '?')} type={chart.get('chartType', '?')}"
    if chart.get("title"):
        attrs += f" title={escape_text(chart['title'], quote=True)}"
    attrs += f" series={chart.get('seriesCount', 0)}"
    if include_points:
        attrs += f" points={chart.get('pointCount', 0)}"
        if chart.get("plots"):
            plot_types = ",".join(str(plot.get("chartType", "unknown")) for plot in chart["plots"])
            attrs += f" plots={escape_text(plot_types, quote=True)}"
    return attrs


def _bar_like_chart_attrs(series: list[ChartSeries]) -> str:
    attrs = _categories_attr(series, ellipsize=True)
    names = _series_names(series)
    if names:
        attrs += f" names={escape_text(','.join(names), quote=True)}"
    return attrs


def _pie_chart_attrs(series: list[ChartSeries]) -> str:
    categories = _collect_categories(series)
    if not categories:
        return ""
    labels = categories[: _constants._X_LABEL_MAX]
    return f" names={escape_text(','.join(labels), quote=True)}"


def _scatter_chart_attrs(chart: InlineObject, series: list[ChartSeries]) -> str:
    attrs = ""
    names = _series_names(series)
    if names:
        attrs += f" names={escape_text(','.join(names), quote=True)}"
    attrs += f" points={chart.get('pointCount', 0)}"
    return attrs


def _stock_chart_attrs(series: list[ChartSeries]) -> str:
    return _categories_attr(series, ellipsize=True)


def _surface_chart_attrs(series: list[ChartSeries]) -> str:
    attrs = ""
    names = _series_names(series)
    if names:
        attrs += f" names={escape_text(','.join(names), quote=True)}"
    attrs += _categories_attr(series, ellipsize=False)
    return attrs


def _categories_attr(series: list[ChartSeries], *, ellipsize: bool) -> str:
    categories = _collect_categories(series)
    if not categories:
        return ""
    labels = categories[: _constants._X_LABEL_MAX]
    category_text = ",".join(labels)
    if ellipsize and len(categories) > _constants._X_LABEL_MAX:
        category_text += ",..."
    return f" categories={escape_text(category_text, quote=True)}"


def _series_names(series: list[ChartSeries]) -> list[str]:
    names: list[str] = []
    for series_item in series:
        name = series_item.get("name", f"S{series_item.get('index', '')}")
        if name:
            names.append(str(name))
    return names


def _collect_categories(series: list[ChartSeries]) -> list[str]:
    categories: list[str] = []
    for series_item in series:
        preview = (series_item.get("preview") or "").split("; ")
        for preview_item in preview:
            if "=" not in preview_item:
                continue
            category = preview_item.split("=", 1)[0]
            if category and category not in categories:
                categories.append(category)
    return categories
