"""chart values."""

from __future__ import annotations

from collections.abc import Iterable
from xml.etree import ElementTree as ET

NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


NS_CX = "http://schemas.microsoft.com/office/drawing/2014/chartex"


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
