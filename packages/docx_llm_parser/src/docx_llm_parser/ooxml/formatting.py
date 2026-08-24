"""Parse OOXML text formatting that is useful for reading semantics."""

from __future__ import annotations

import re
from typing import cast
from xml.etree import ElementTree as ET

from ..core.constants import attr, first_child, is_on
from ..core.models import ParagraphBorder, ParagraphBorders, RunFormat

VISIBLE_FORMAT_KEYS = (
    "bold",
    "italic",
    "underline",
    "strike",
    "superscript",
    "subscript",
    "smallCaps",
    "color",
    "highlight",
    "bg",
)


def parse_run_format(run_properties: ET.Element | None) -> RunFormat:
    """Extract lightweight formatting from w:rPr that the final text may need to preserve."""
    if run_properties is None:
        return {}

    fmt: RunFormat = {}
    _read_bool_format(run_properties, "b", "bold", fmt)
    _read_bool_format(run_properties, "i", "italic", fmt)
    _read_underline(run_properties, fmt)
    _read_strike(run_properties, fmt)
    _read_vert_align(run_properties, fmt)
    _read_bool_format(run_properties, "smallCaps", "smallCaps", fmt)
    _read_color(run_properties, fmt)
    _read_highlight(run_properties, fmt)
    _read_background(run_properties, fmt)
    return fmt


def parse_paragraph_alignment(paragraph_properties: ET.Element | None) -> str | None:
    """Read an explicit Word paragraph alignment value."""
    if paragraph_properties is None:
        return None
    node = first_child(paragraph_properties, "w", "jc")
    if node is None:
        return None
    value = attr(node, "w", "val")
    return value.lower() if value else None


def parse_paragraph_borders(paragraph_properties: ET.Element | None) -> ParagraphBorders:
    """Read visible paragraph border sides and their colors."""
    if paragraph_properties is None:
        return {}
    border_properties = first_child(paragraph_properties, "w", "pBdr")
    if border_properties is None:
        return {}
    borders: ParagraphBorders = {}
    for side in ("top", "left", "bottom", "right", "between", "bar"):
        node = first_child(border_properties, "w", side)
        if node is None:
            continue
        style = (attr(node, "w", "val") or "").lower()
        if style in {"", "nil", "none"}:
            continue
        border: ParagraphBorder = {"style": style}
        color = normalize_hex_color(attr(node, "w", "color"))
        if color:
            border["color"] = color
        size = attr(node, "w", "sz")
        if size:
            border["size"] = size
        borders[side] = border
    return borders


def merge_paragraph_borders(*borders: ParagraphBorders | None) -> ParagraphBorders:
    """Merge paragraph border sides in style-inheritance order."""
    merged: ParagraphBorders = {}
    for item in borders:
        if item:
            merged.update({side: cast(ParagraphBorder, dict(value)) for side, value in item.items()})
    return merged


def merge_run_formats(*formats: RunFormat | None) -> RunFormat:
    """Merge formats in inheritance order; later explicit values override earlier ones."""
    merged: RunFormat = {}
    for fmt in formats:
        if not fmt:
            continue
        for key, value in fmt.items():
            if key not in VISIBLE_FORMAT_KEYS:
                continue
            if value is False or value is None or value == "":
                # When explicitly disabled, remove the inherited visible format.
                merged.pop(key, None)
            else:
                merged[key] = value
    return merged


def visible_run_format(fmt: RunFormat | None) -> RunFormat:
    """Filter down to the set of formats the final XML needs to express."""
    if not fmt:
        return {}
    return {
        key: value for key, value in fmt.items() if key in VISIBLE_FORMAT_KEYS and value is not False and value not in {None, ""}
    }


def _read_bool_format(run_properties: ET.Element, child_name: str, key: str, fmt: RunFormat) -> None:
    """Read boolean run attributes such as b/i."""
    node = first_child(run_properties, "w", child_name)
    if node is not None:
        fmt[key] = is_on(node)


def _read_underline(run_properties: ET.Element, fmt: RunFormat) -> None:
    """Read underline; only its presence matters in the end, not the specific line style."""
    node = first_child(run_properties, "w", "u")
    if node is None:
        return
    val = (attr(node, "w", "val") or "single").lower()
    fmt["underline"] = val not in {"0", "false", "off", "none"}


def _read_strike(run_properties: ET.Element, fmt: RunFormat) -> None:
    """Read strike and double strike; both are ultimately expressed as strike."""
    strike = first_child(run_properties, "w", "strike")
    double_strike = first_child(run_properties, "w", "dstrike")
    if strike is not None:
        fmt["strike"] = is_on(strike)
    if double_strike is not None:
        fmt["strike"] = is_on(double_strike)


def _read_vert_align(run_properties: ET.Element, fmt: RunFormat) -> None:
    """Read superscript/subscript markers (w:vertAlign)."""
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
    """Read the font color; theme color mapping is deferred to a later theme parsing pass."""
    node = first_child(run_properties, "w", "color")
    if node is None:
        return
    value = normalize_hex_color(attr(node, "w", "val"))
    if value and not is_default_text_color(value):
        fmt["color"] = value


def _read_highlight(run_properties: ET.Element, fmt: RunFormat) -> None:
    """Read Word text highlight."""
    node = first_child(run_properties, "w", "highlight")
    if node is None:
        return
    value = attr(node, "w", "val")
    if value and value.lower() != "none":
        fmt["highlight"] = value
    else:
        fmt["highlight"] = None


def _read_background(run_properties: ET.Element, fmt: RunFormat) -> None:
    """Read the run's shading background color."""
    node = first_child(run_properties, "w", "shd")
    if node is None:
        return
    value = normalize_hex_color(attr(node, "w", "fill"))
    if value:
        fmt["bg"] = value


def normalize_hex_color(value: str | None) -> str | None:
    """Normalize OOXML six-digit colors to #RRGGBB; other valid values are kept as-is."""
    if not value or value.lower() == "auto":
        return None
    if re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        return "#" + value.upper()
    return value


def is_default_text_color(value: str) -> bool:
    """Filter out font colors close to the default black to reduce noise in the final XML."""
    lowered = value.lower()
    if lowered in {"black", "#000000"}:
        return True
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return False
    red = int(value[1:3], 16)
    green = int(value[3:5], 16)
    blue = int(value[5:7], 16)
    return max(red, green, blue) <= 48 and max(red, green, blue) - min(red, green, blue) <= 16
