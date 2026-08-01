"""图表 inline 渲染与 extract 辅助。"""

from __future__ import annotations

from html import escape

from ...core.models import Chart, ChartSeries, InlineObject, ResourceDetail
from .. import _constants


def chart_to_html5(obj: InlineObject) -> str:
    """L2：输出图表轻量摘要（使用语义属性名）。"""
    chart_id = obj.get("id", "?")
    chart_type = obj.get("chartType", "?")

    attrs = f"id={chart_id} type={chart_type}"
    if obj.get("title"):
        attrs += f" title={escape(obj['title'], quote=True)}"
    attrs += f" series={obj.get('seriesCount', 0)}"

    type_attrs = chart_type_attrs(obj, chart_type)
    if type_attrs:
        attrs += type_attrs

    extract_hint = f'\n<!-- Use extract("chart", "{chart_id}") for full data. -->'

    series = obj.get("series") or []
    if not series:
        return f"<chart {attrs}>" + extract_hint

    parts = [f"<chart {attrs}>"]
    for item in series[: _constants._CHART_SERIES_TRUNCATE]:
        s_attrs = f"n={escape(item.get('name', '?'), quote=True)} p={item['pointCount']}"
        if "min" in item:
            s_attrs += f" min={item['min']}"
        if "max" in item:
            s_attrs += f" max={item['max']}"
        if item.get("preview"):
            s_attrs += f" pv={escape(item['preview'], quote=True)}"
        parts.append(f"<s {s_attrs}/>")
    if len(series) > _constants._CHART_SERIES_TRUNCATE:
        parts.append(f"<ms c={len(series) - _constants._CHART_SERIES_TRUNCATE}/>")
    parts.append("</chart>")
    parts.append(extract_hint)
    return "".join(parts)


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
                attrs += f" x={escape(x_val, quote=True)}"
            names = [s.get("name", f"S{s.get('index', '')}") for s in series]
            if names:
                attrs += f" names={escape(','.join(names), quote=True)}"
            range_val = _series_range(series)
            if range_val:
                attrs += f" range={escape(range_val, quote=True)}"

    elif chart_type in ("pie", "pie3d", "doughnut"):
        if series:
            names = _all_categories(series)
            if names:
                attrs += f" names={escape(','.join(names[: _constants._X_LABEL_MAX]), quote=True)}"
            range_val = _series_range(series)
            if range_val:
                attrs += f" range={escape(range_val, quote=True)}"

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
                attrs += f" x={escape(x_val, quote=True)}"

    elif chart_type in ("surface", "surface3d") and series:
        names = [s.get("name", f"S{s.get('index', '')}") for s in series]
        if names:
            attrs += f" names={escape(','.join(names), quote=True)}"
        cats = _all_categories(series)
        if cats:
            attrs += f" x={escape(','.join(cats[: _constants._X_LABEL_MAX]), quote=True)}"

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


def _series_range(series: list[ChartSeries]) -> str | None:
    """计算所有系列的数值范围。"""
    mins: list[float] = []
    maxs: list[float] = []
    for s in series:
        if "min" in s:
            mins.append(s["min"])
        if "max" in s:
            maxs.append(s["max"])
    if mins and maxs:
        return f"{min(mins)}~{max(maxs)}"
    return None


def extract_chart_item(c: Chart) -> ResourceDetail:
    """构建 extract("chart") 的完整返回项。"""
    item: ResourceDetail = {
        "id": c.get("id", ""),
        "chartType": c.get("chartType", "?"),
        "seriesCount": c.get("seriesCount", 0),
        "pointCount": c.get("pointCount", 0),
    }
    if c.get("title"):
        item["title"] = c["title"]

    series = c.get("series") or []
    item_series = []
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
        preview = (s.get("preview") or "").split("; ")
        if preview:
            s_item["points"] = preview[: _constants._EXTRACT_POINTS_LIMIT]
            if len(preview) > _constants._EXTRACT_POINTS_LIMIT:
                s_item["truncated"] = True
        item_series.append(s_item)
    item["series"] = item_series
    return item
