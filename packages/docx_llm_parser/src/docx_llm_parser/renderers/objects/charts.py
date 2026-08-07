"""图表 inline 渲染与 extract 辅助。"""

from __future__ import annotations

from html import escape

from ...core.models import Chart, ChartSeries, InlineObject, ResourceDetail
from .. import _constants


def chart_to_html5(obj: InlineObject) -> str:
    """semantic：输出图表轻量摘要。完整数据点通过 get_resource 获取。"""
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
    """按图表类型返回差异化属性的 HTML 字符串。"""
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
    """从所有系列的预览数据中提取分类标签。"""
    cats: list[str] = []
    for s in series:
        preview = (s.get("preview") or "").split("; ")
        for pv in preview:
            if "=" in pv:
                cat = pv.split("=", 1)[0]
                if cat and cat not in cats:
                    cats.append(cat)
    return cats


def extract_chart_item(c: Chart) -> ResourceDetail:
    """构建 extract("chart") 的完整返回项 — 包含全部数据点。"""
    item: ResourceDetail = {
        "id": c.get("id", ""),
        "chartType": c.get("chartType", "?"),
        "seriesCount": c.get("seriesCount", 0),
        "pointCount": c.get("pointCount", 0),
    }
    if c.get("title"):
        item["title"] = c["title"]

    series = c.get("series") or []
    item_series: list[ResourceDetail] = []
    for s in series:
        s_item: ResourceDetail = {
            "index": s.get("index", 0),
            "pointCount": s.get("pointCount", 0),
        }
        if s.get("name"):
            s_item["name"] = s["name"]
        if "min" in s:
            s_item["min"] = s["min"]
        if "max" in s:
            s_item["max"] = s["max"]

        # Build full data points from categories + values arrays
        cats = s.get("categories", [])
        vals = s.get("values", [])
        points: list[dict[str, str]] = []
        for i in range(max(len(cats), len(vals))):
            pt: dict[str, str] = {}
            if i < len(cats):
                pt["category"] = cats[i]
            if i < len(vals):
                pt["value"] = vals[i]
            if pt:
                points.append(pt)
        if points:
            s_item["points"] = points

        item_series.append(s_item)
    item["series"] = item_series
    return item
