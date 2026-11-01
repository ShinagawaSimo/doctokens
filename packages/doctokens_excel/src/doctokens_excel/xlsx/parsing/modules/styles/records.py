"""Semantic style records and theme-color resolution for SpreadsheetML."""

from __future__ import annotations

from typing import TypedDict
from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from ....model.rules import ConditionalStyle
from .colors import SpreadsheetColors

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


class FontInfo(TypedDict, total=False):
    bold: bool
    italic: bool
    underline: bool
    strike: bool
    superscript: bool
    subscript: bool
    color: str


class FillInfo(TypedDict, total=False):
    fill: str


def font_info(
    font: ET.Element, colors: SpreadsheetColors, *, warnings: list[ParseWarning] | None = None, locator: str = ""
) -> FontInfo:
    """Extract the semantic font properties used by the renderer."""
    info: FontInfo = {"bold": False, "italic": False, "underline": False}
    bold, italic, underline = (font.find(f"{{{NS_S}}}{tag}") for tag in ("b", "i", "u"))
    if bold is not None:
        info["bold"] = bold.get("val", "1").lower() not in {"0", "false", "off"}
    if italic is not None:
        info["italic"] = italic.get("val", "1").lower() not in {"0", "false", "off"}
    if underline is not None:
        info["underline"] = underline.get("val", "single").lower() not in {"0", "false", "off", "none"}
    strike = font.find(f"{{{NS_S}}}strike")
    if strike is not None:
        info["strike"] = strike.get("val", "1").lower() not in {"0", "false", "off"}
    vertical = font.find(f"{{{NS_S}}}vertAlign")
    if vertical is not None:
        info["superscript"] = vertical.get("val") == "superscript"
        info["subscript"] = vertical.get("val") == "subscript"
    color = font.find(f"{{{NS_S}}}color")
    if color is not None:
        resolved = colors.resolve(color, warnings=warnings, locator=locator)
        if resolved:
            info["color"] = f"#{resolved}"
    return info


def fill_info(
    fill: ET.Element, colors: SpreadsheetColors, *, warnings: list[ParseWarning] | None = None, locator: str = ""
) -> FillInfo:
    """Extract the semantic foreground fill color."""
    info: FillInfo = {}
    pattern_fill = fill.find(f"{{{NS_S}}}patternFill")
    if pattern_fill is not None:
        foreground = pattern_fill.find(f"{{{NS_S}}}fgColor")
        if foreground is not None:
            resolved = colors.resolve(foreground, warnings=warnings, locator=locator)
            if resolved:
                info["fill"] = f"#{resolved}"
    return info


def differential_style(
    dxf: ET.Element, colors: SpreadsheetColors, *, warnings: list[ParseWarning] | None = None, locator: str = ""
) -> ConditionalStyle:
    """Summarize meaningful ``<dxf>`` fields for conditional formatting."""
    style: ConditionalStyle = {}
    font = dxf.find(f"{{{NS_S}}}font")
    if font is not None:
        font_details = font_info(font, colors, warnings=warnings, locator=locator)
        for tag, key in (("b", "bold"), ("i", "italic"), ("u", "underline"), ("strike", "strike")):
            if font.find(f"{{{NS_S}}}{tag}") is not None:
                style[key] = bool(font_details.get(key))  # type: ignore[literal-required]
        if color := font_details.get("color"):
            style["color"] = color
    fill = dxf.find(f"{{{NS_S}}}fill")
    if fill is not None:
        fill_details = fill_info(fill, colors, warnings=warnings, locator=locator)
        if color := fill_details.get("fill"):
            style["fill"] = color
    num_fmt = dxf.find(f"{{{NS_S}}}numFmt")
    if num_fmt is not None and (code := num_fmt.get("formatCode")):
        style["number_format"] = code
    return style
