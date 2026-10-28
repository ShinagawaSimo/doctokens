"""Decode explicit Word character elements without guessing unknown font glyphs."""

from __future__ import annotations

import re
from collections.abc import Callable
from xml.etree import ElementTree as ET

from doctokens_core.ooxml.symbols import symbol_character

from .namespaces import attr, qualified_name


def word_character(node: ET.Element, warn: Callable[[str, str], None]) -> str | None:
    if node.tag == qualified_name("w", "noBreakHyphen"):
        return "\u2011"
    if node.tag == qualified_name("w", "softHyphen"):
        # Discretionary line-layout glyphs have no character in unbroken reading.
        return ""
    if node.tag != qualified_name("w", "sym"):
        return None
    font = attr(node, "w", "font") or ""
    value = attr(node, "w", "char") or ""
    if not re.fullmatch(r"[0-9A-Fa-f]{4}", value):
        warn("INVALID_SYMBOL_CODE", f"Invalid Word symbol code {value!r}")
        return "\ufffd"
    character = symbol_character(font, int(value, 16))
    if character is None:
        warn("SYMBOL_UNSUPPORTED", f"Cannot decode Word symbol {value!r} in font {font!r}")
        return "\ufffd"
    return character
