"""Resolve DrawingML list declarations without interpreting symbol codes as prose."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.text_numbering import format_drawingml_autonumber

from ....core.constants import first_child
from ....core.models import Paragraph, ParagraphStyle
from ....ooxml.bullet_fonts import font_declaration, text_font

_SYMBOL_FONTS = {"wingdings", "wingdings 2", "wingdings 3", "webdings", "symbol"}
# Only mappings with a known glyph are interpreted; the rest remain source evidence.
_BULLET_GLYPHS = {
    "wingdings": {0x6C: "●", 0x6E: "■", 0x75: "◆", 0xA7: "▪"},
    "symbol": {0xB7: "•"},
}


def integer(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def list_metadata(p: ET.Element, inherited: ParagraphStyle) -> Paragraph:
    pr = first_child(p, "a", "pPr")
    result: Paragraph = {}
    if pr is not None and first_child(pr, "a", "buNone") is not None:
        return result
    bullet = first_child(pr, "a", "buChar") if pr is not None else None
    auto = first_child(pr, "a", "buAutoNum") if pr is not None else None
    if bullet is not None:
        result["bullet"] = bullet.get("char") or "•"
    elif auto is not None:
        result["numberType"] = auto.get("type", "arabicPeriod")
        result["startAt"] = integer(auto.get("startAt"), inherited.get("startAt", 1))
    elif inherited.get("listNone"):
        return result
    elif inherited.get("bullet"):
        result["bullet"] = inherited["bullet"]
    elif inherited.get("numberType"):
        result["numberType"] = inherited["numberType"]
        result["startAt"] = inherited.get("startAt", 1)
    if "bullet" not in result:
        return result
    font, symbol = _bullet_font(p, pr, inherited)
    source = result["bullet"]
    font_key = font.strip().casefold()
    private = any(0xE000 <= ord(char) <= 0xF8FF for char in source)
    if font_key in _SYMBOL_FONTS or symbol or private:
        mapping = _BULLET_GLYPHS.get(font_key, {})
        resolved = "".join(mapping.get(ord(char) - 0xF000 if 0xF000 <= ord(char) <= 0xF0FF else ord(char), "") for char in source)
        result["bullet"] = resolved if len(resolved) == len(source) else "•"
        result["bulletSource"] = source
        if font:
            result["bulletFont"] = font
    return result


def _bullet_font(p: ET.Element, pr: ET.Element | None, inherited: ParagraphStyle) -> tuple[str, bool]:
    font = inherited.get("bulletFont", "")
    symbol = inherited.get("bulletFontSymbol", False)
    if pr is not None:
        direct = first_child(pr, "a", "buFont")
        if direct is not None:
            font, symbol = font_declaration(direct)
        elif first_child(pr, "a", "buFontTx") is not None:
            font, symbol = "", False
    if font:
        return font, symbol
    declaration = (inherited.get("textFont", ""), inherited.get("textFontSymbol", False))
    defaults = text_font(first_child(pr, "a", "defRPr") if pr is not None else None)
    if defaults is not None:
        declaration = defaults
    for child in p:
        if first_child(child, "a", "t") is not None:
            direct_font = text_font(first_child(child, "a", "rPr"))
            if direct_font is not None:
                declaration = direct_font
            break
    return declaration


def list_prefix(metadata: Paragraph, level: int, counters: dict[tuple[str, int], int]) -> str:
    if bullet := metadata.get("bullet"):
        return bullet + " "
    if number_type := metadata.get("numberType"):
        key = (number_type, level)
        counters[key] = counters[key] + 1 if key in counters else metadata.get("startAt", 1)
        metadata["number"] = counters[key]
        return format_drawingml_autonumber(counters[key], number_type) + " "
    return ""
