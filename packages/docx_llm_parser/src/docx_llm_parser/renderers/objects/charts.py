"""Chart inline rendering and extract helpers."""

from __future__ import annotations

from html import escape

from ...core.models import Chart, ChartSeries, InlineObject
from .. import _constants


def chart_to_html5(obj: InlineObject) -> str:
    """semantic: output a lightweight chart summary. Full data points are available via get_resource."""
    chart_id = obj.get("id", "?")
    chart_type = obj.get("chartType", "?")

    attrs = f"id={chart_id} type={chart_type}"
    if obj.get("title"):
        attrs += f" title={escape(obj['title'], quote=True)}"
    attrs += f" series={obj.get('seriesCount', 0)}"

    type_attrs = chart_type_attrs(obj, chart_type)
    if type_attrs:
        attrs += type_attrs

    attrs += " truncated"
    return f"<chart {attrs}>\n"


def chart_type_attrs(obj: InlineObject, chart_type: str) -> str:
    """Return an HTML string with attributes differentiated by chart type."""
    attrs = ""
    series = obj.get("series") or []

    if chart_type in ("bar", "bar3d", "line", "line3d", "area", "area3d", "radar"):
        if series:
            cats = _all_categories(series)
            if cats:
                labels = cats[: _constants._X_LABEL_MAX]
                x_val = ",".join(labels)
                if len(cats) > _constants._X_LABEL_MAX:
                    x_val += ",..."
                attrs += f" categories={escape(x_val, quote=True)}"
            names = [s.get("name", f"S{s.get('index', '')}") for s in series]
            if names:
                attrs += f" names={escape(','.join(names), quote=True)}"

    elif chart_type in ("pie", "pie3d", "doughnut"):
        if series:
            names = _all_categories(series)
            if names:
                attrs += f" names={escape(','.join(names[: _constants._X_LABEL_MAX]), quote=True)}"

    elif chart_type == "scatter" or chart_type == "bubble":
        if series:
            names = [s.get("name", f"S{s.get('index', '')}") for s in series]
            if names:
                attrs += f" names={escape(','.join(names), quote=True)}"
        attrs += f" points={obj.get('pointCount', 0)}"

    elif chart_type == "stock":
        if series:
            cats = _all_categories(series)
            if cats:
                labels = cats[: _constants._X_LABEL_MAX]
                x_val = ",".join(labels)
                if len(cats) > _constants._X_LABEL_MAX:
                    x_val += ",..."
                attrs += f" categories={escape(x_val, quote=True)}"

    elif chart_type in ("surface", "surface3d") and series:
        names = [s.get("name", f"S{s.get('index', '')}") for s in series]
        if names:
            attrs += f" names={escape(','.join(names), quote=True)}"
        cats = _all_categories(series)
        if cats:
            attrs += f" categories={escape(','.join(cats[: _constants._X_LABEL_MAX]), quote=True)}"

    return attrs


def _all_categories(series: list[ChartSeries]) -> list[str]:
    """Extract category labels from the preview data of all series."""
    cats: list[str] = []
    for s in series:
        preview = (s.get("preview") or "").split("; ")
        for pv in preview:
            if "=" in pv:
                cat = pv.split("=", 1)[0]
                if cat and cat not in cats:
                    cats.append(cat)
    return cats


def render_chart_resource(c: Chart) -> str:
    """Render a chart as an HTML string for get_resource — full data points."""
    chart_id = c.get("id", "?")
    chart_type = c.get("chartType", "?")

    attrs = f"id={chart_id} type={chart_type}"
    if c.get("title"):
        attrs += f" title={escape(c['title'], quote=True)}"
    attrs += f" series={c.get('seriesCount', 0)} points={c.get('pointCount', 0)}"
    parts = [f"<chart {attrs}>"]

    for s in c.get("series") or []:
        s_attrs = f"index={s.get('index', 0)}"
        if s.get("name"):
            s_attrs += f" name={escape(s['name'], quote=True)}"
        if "min" in s:
            s_attrs += f" min={s['min']}"
        if "max" in s:
            s_attrs += f" max={s['max']}"
        parts.append(f"\n<series {s_attrs}>")

        cats = s.get("categories", [])
        vals = s.get("values", [])
        for i in range(max(len(cats), len(vals))):
            pt_attrs = ""
            if i < len(cats):
                pt_attrs += f" category={escape(cats[i], quote=True)}"
            if i < len(vals):
                pt_attrs += f" value={escape(vals[i], quote=True)}"
            parts.append(f"\n<point{pt_attrs}/>")

    return "".join(parts)
