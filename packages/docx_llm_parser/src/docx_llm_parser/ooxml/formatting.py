"""解析 OOXML 中对阅读语义有用的文字格式。"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from ..core.constants import attr, first_child, is_on
from ..core.models import RunFormat

VISIBLE_FORMAT_KEYS = (
    "bold",
    "italic",
    "underline",
    "strike",
    "superscript",
    "subscript",
    "color",
    "highlight",
    "bg",
)


def parse_run_format(run_properties: ET.Element | None) -> RunFormat:
    """从 w:rPr 提取最终文本可能需要保留的轻量格式。"""
    if run_properties is None:
        return {}

    fmt: RunFormat = {}
    _read_bool_format(run_properties, "b", "bold", fmt)
    _read_bool_format(run_properties, "i", "italic", fmt)
    _read_underline(run_properties, fmt)
    _read_strike(run_properties, fmt)
    _read_vert_align(run_properties, fmt)
    _read_color(run_properties, fmt)
    _read_highlight(run_properties, fmt)
    _read_background(run_properties, fmt)
    return fmt


def merge_run_formats(*formats: RunFormat | None) -> RunFormat:
    """按继承顺序合并格式，后面的显式值覆盖前面的值。"""
    merged: RunFormat = {}
    for fmt in formats:
        if not fmt:
            continue
        for key, value in fmt.items():
            if key not in VISIBLE_FORMAT_KEYS:
                continue
            if value is False or value is None or value == "":
                # 显式关闭时移除继承来的可见格式。
                merged.pop(key, None)
            else:
                merged[key] = value
    return merged


def visible_run_format(fmt: RunFormat | None) -> RunFormat:
    """过滤成最终 XML 需要表达的格式集合。"""
    if not fmt:
        return {}
    return {
        key: value
        for key, value in fmt.items()
        if key in VISIBLE_FORMAT_KEYS and value is not False and value not in {None, ""}
    }


def _read_bool_format(
    run_properties: ET.Element, child_name: str, key: str, fmt: RunFormat
) -> None:
    """读取 b/i 这类布尔 run 属性。"""
    node = first_child(run_properties, "w", child_name)
    if node is not None:
        fmt[key] = is_on(node)


def _read_underline(run_properties: ET.Element, fmt: RunFormat) -> None:
    """读取下划线；最终只关心有没有下划线，不暴露具体线型。"""
    node = first_child(run_properties, "w", "u")
    if node is None:
        return
    val = (attr(node, "w", "val") or "single").lower()
    fmt["underline"] = val not in {"0", "false", "off", "none"}


def _read_strike(run_properties: ET.Element, fmt: RunFormat) -> None:
    """读取删除线和双删除线，最终都表达为 strike。"""
    strike = first_child(run_properties, "w", "strike")
    double_strike = first_child(run_properties, "w", "dstrike")
    if strike is not None:
        fmt["strike"] = is_on(strike)
    if double_strike is not None:
        fmt["strike"] = is_on(double_strike)


def _read_vert_align(run_properties: ET.Element, fmt: RunFormat) -> None:
    """读取上标/下标标记（w:vertAlign）。"""
    node = first_child(run_properties, "w", "vertAlign")
    if node is None:
        return
    val = (attr(node, "w", "val") or "").lower()
    if val == "superscript":
        fmt["superscript"] = True
        fmt.pop("subscript", None)
    elif val == "subscript":
        fmt["subscript"] = True
        fmt.pop("superscript", None)


def _read_color(run_properties: ET.Element, fmt: RunFormat) -> None:
    """读取字体颜色；主题色映射暂留给后续主题解析。"""
    node = first_child(run_properties, "w", "color")
    if node is None:
        return
    value = normalize_hex_color(attr(node, "w", "val"))
    if value and not is_default_text_color(value):
        fmt["color"] = value


def _read_highlight(run_properties: ET.Element, fmt: RunFormat) -> None:
    """读取 Word 文本高亮。"""
    node = first_child(run_properties, "w", "highlight")
    if node is None:
        return
    value = attr(node, "w", "val")
    if value and value.lower() != "none":
        fmt["highlight"] = value
    else:
        fmt["highlight"] = None


def _read_background(run_properties: ET.Element, fmt: RunFormat) -> None:
    """读取 run 底纹背景色。"""
    node = first_child(run_properties, "w", "shd")
    if node is None:
        return
    value = normalize_hex_color(attr(node, "w", "fill"))
    if value:
        fmt["bg"] = value


def normalize_hex_color(value: str | None) -> str | None:
    """把 OOXML 六位颜色统一成 #RRGGBB，其它有效值原样保留。"""
    if not value or value.lower() == "auto":
        return None
    if re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        return "#" + value.upper()
    return value


def is_default_text_color(value: str) -> bool:
    """过滤接近默认黑色的字体色，减少最终 XML 噪声。"""
    lowered = value.lower()
    if lowered in {"black", "#000000"}:
        return True
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return False
    red = int(value[1:3], 16)
    green = int(value[3:5], 16)
    blue = int(value[5:7], 16)
    return max(red, green, blue) <= 48 and max(red, green, blue) - min(red, green, blue) <= 16
