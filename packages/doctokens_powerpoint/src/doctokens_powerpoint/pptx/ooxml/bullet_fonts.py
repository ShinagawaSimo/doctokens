"""Font declarations required to interpret a bullet, independent of typography output."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from .namespaces import first_child


def font_declaration(node: ET.Element) -> tuple[str, bool]:
    charset = node.get("charset", "")
    try:
        symbol = int(charset, 16) == 2
    except ValueError:
        symbol = False
    return node.get("typeface", ""), symbol


def text_font(properties: ET.Element | None) -> tuple[str, bool] | None:
    if properties is not None:
        for name in ("sym", "latin"):
            font = first_child(properties, "a", name)
            if font is not None:
                return font_declaration(font)
    return None
