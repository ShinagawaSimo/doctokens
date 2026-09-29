"""Semantic style records and theme-color resolution for SpreadsheetML."""

from __future__ import annotations

from typing import TypedDict
from xml.etree import ElementTree as ET

from ooxml_llm_core.package import PackageReader

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


class FontInfo(TypedDict, total=False):
    bold: bool
    italic: bool
    underline: bool
    color: str


class FillInfo(TypedDict, total=False):
    fill: str


# Spreadsheet theme color index order.
_THEME_SLOTS = [
    "lt1",
    "dk1",
    "lt2",
    "dk2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
]

# Office default theme colors (fallback when theme1.xml is absent).
_DEFAULT_THEME: dict[int, str] = dict(
    enumerate(
        [
            "FFFFFF",
            "000000",
            "E7E6E6",
            "44546A",
            "4472C4",
            "ED7D31",
            "A5A5A5",
            "FFC000",
            "5B9BD5",
            "70AD47",
            "0563C1",
            "954F72",
        ]
    )
)


def parse_theme(pkg: PackageReader) -> dict[int, str]:
    """Parse ``xl/theme/theme1.xml`` into theme-indexed RGB values."""
    if not pkg.exists("xl/theme/theme1.xml"):
        return _DEFAULT_THEME.copy()

    root = pkg.read_xml("xl/theme/theme1.xml")
    scheme = root.find(f"{{{NS_A}}}themeElements/{{{NS_A}}}clrScheme")
    if scheme is None:
        return _DEFAULT_THEME.copy()

    mapping: dict[int, str] = {}
    for index, slot in enumerate(_THEME_SLOTS):
        resolved = _theme_slot_value(scheme.find(f"{{{NS_A}}}{slot}"))
        mapping[index] = resolved or _DEFAULT_THEME.get(index, "000000")
    return mapping


def font_info(font: ET.Element, theme: dict[int, str]) -> FontInfo:
    """Extract the semantic font properties used by the renderer."""
    info: FontInfo = {"bold": False, "italic": False, "underline": False}
    if font.find(f"{{{NS_S}}}b") is not None:
        info["bold"] = True
    if font.find(f"{{{NS_S}}}i") is not None:
        info["italic"] = True
    if font.find(f"{{{NS_S}}}u") is not None:
        info["underline"] = True
    color = font.find(f"{{{NS_S}}}color")
    if color is not None:
        resolved = resolve_color(color, theme)
        if resolved:
            info["color"] = f"#{resolved}"
    return info


def fill_info(fill: ET.Element, theme: dict[int, str]) -> FillInfo:
    """Extract the semantic foreground fill color."""
    info: FillInfo = {}
    pattern_fill = fill.find(f"{{{NS_S}}}patternFill")
    if pattern_fill is not None:
        foreground = pattern_fill.find(f"{{{NS_S}}}fgColor")
        if foreground is not None:
            resolved = resolve_color(foreground, theme)
            if resolved:
                info["fill"] = f"#{resolved}"
    return info


def differential_style(dxf: ET.Element, theme: dict[int, str]) -> str:
    """Summarize meaningful ``<dxf>`` fields for conditional formatting."""
    parts: list[str] = []
    font = dxf.find(f"{{{NS_S}}}font")
    if font is not None:
        font_details = font_info(font, theme)
        if font_details.get("bold"):
            parts.append("bold")
        if font_details.get("italic"):
            parts.append("italic")
        if font_details.get("underline"):
            parts.append("underline")
        if color := font_details.get("color"):
            parts.append(f"color={color}")
    fill = dxf.find(f"{{{NS_S}}}fill")
    if fill is not None:
        fill_details = fill_info(fill, theme)
        if color := fill_details.get("fill"):
            parts.append(f"fill={color}")
    num_fmt = dxf.find(f"{{{NS_S}}}numFmt")
    if num_fmt is not None and (code := num_fmt.get("formatCode")):
        parts.append(f"numberFormat={code}")
    alignment = dxf.find(f"{{{NS_S}}}alignment")
    if alignment is not None:
        parts.extend(f"{key}={value}" for key in ("horizontal", "vertical", "wrapText") if (value := alignment.get(key)))
    return " ".join(parts)


def _theme_slot_value(elem: ET.Element | None) -> str | None:
    if elem is None:
        return None
    srgb = elem.find(f"{{{NS_A}}}srgbClr")
    if srgb is not None and (value := srgb.get("val")):
        return value
    sys_color = elem.find(f"{{{NS_A}}}sysClr")
    if sys_color is not None and (value := sys_color.get("lastClr")):
        return value
    return None


def resolve_color(color_elem: ET.Element, theme: dict[int, str]) -> str | None:
    """Resolve an OOXML ``<color>`` element to an ``RRGGBB`` value."""
    rgb = color_elem.get("rgb")
    if rgb and rgb != "00000000":
        return _rgb_hex(rgb)

    theme_str = color_elem.get("theme")
    if theme_str is not None:
        try:
            base = theme.get(int(theme_str))
        except ValueError:
            base = None
        if base is not None:
            tint_str = color_elem.get("tint")
            if tint_str is not None:
                try:
                    return apply_tint(base, float(tint_str))
                except ValueError:
                    pass
            return base
    return None


def _rgb_hex(rgb: str) -> str:
    """Normalize OOXML color (AARRGGBB or RRGGBB) to RRGGBB."""
    return rgb[2:] if len(rgb) == 8 else rgb


def apply_tint(rgb_hex: str, tint: float) -> str:
    """Apply an OOXML tint, moving RGB values toward black or white."""
    if tint == 0:
        return rgb_hex

    channels = (int(rgb_hex[index : index + 2], 16) for index in (0, 2, 4))
    if tint < 0:
        factor = 1 + tint
        result = (max(0, min(255, int(channel * factor))) for channel in channels)
    else:
        result = (max(0, min(255, int(channel * (1 - tint) + 255 * tint))) for channel in channels)
    return "".join(f"{channel:02X}" for channel in result)


__all__ = [
    "FillInfo",
    "FontInfo",
    "differential_style",
    "fill_info",
    "font_info",
    "parse_theme",
]
