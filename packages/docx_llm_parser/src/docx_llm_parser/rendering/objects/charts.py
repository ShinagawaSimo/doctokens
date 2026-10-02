"""Chart inline rendering and resource rendering helpers."""

from __future__ import annotations

from html import escape as escape_text

from ooxml_llm_core.doctokens_xml import append, element
from ooxml_llm_core.resource_xml import resource_document

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
    if chart.get("plots"):
        node.set("plots", ",".join(str(p.get("chartType", "unknown")) for p in chart["plots"]))
    if combination:
        for plot in chart.get("plots") or []:
            indices = plot.get("seriesIndices", [])
            append(
                node,
                "plot",
                index=plot.get("index", 0),
                type=plot.get("chartType", "unknown"),
                series=",".join(str(i) for i in indices) if indices else None,
            )
    for series in chart.get("series") or []:
        child = append(
            node,
            "series",
            index=series.get("index", 0),
            name=series.get("name") or None,
            min=series.get("min"),
            max=series.get("max"),
            type=series.get("chartType") if combination else None,
            hidden=True if series.get("hidden") else None,
        )
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
