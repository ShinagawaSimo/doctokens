"""Decode SpreadsheetML string text once, preserving run boundaries and literal escapes."""

from __future__ import annotations

import re
from collections.abc import Callable
from xml.etree import ElementTree as ET

from ....model.workbook import RichTextRun
from ..styles.records import font_info

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_ESCAPE = re.compile(r"_x([0-9A-Fa-f]{4})_")
WarningSink = Callable[[str, str], None]


def decode_xstring(value: str, warn: WarningSink) -> str:
    """Decode one ST_Xstring layer, then combine saved UTF-16 surrogate pairs."""
    if "_x" not in value:
        return value
    decoded = _ESCAPE.sub(lambda match: chr(int(match[1], 16)), value)
    if decoded == value:
        return value
    pieces: list[str] = []
    invalid: set[int] = set()
    index = 0
    while index < len(decoded):
        code = ord(decoded[index])
        if 0xD800 <= code <= 0xDBFF and index + 1 < len(decoded) and 0xDC00 <= ord(decoded[index + 1]) <= 0xDFFF:
            code = 0x10000 + ((code - 0xD800) << 10) + ord(decoded[index + 1]) - 0xDC00
            index += 1
        if code in {9, 10, 13} or 0x20 <= code <= 0xD7FF or 0xE000 <= code <= 0xFFFD or 0x10000 <= code <= 0x10FFFF:
            pieces.append(chr(code))
        else:
            pieces.append("\ufffd")
            invalid.add(code)
        index += 1
    for code in sorted(invalid):
        warn(
            "XSTRING_CHARACTER_UNREPRESENTABLE", f"Saved character U+{code:04X} cannot be represented in XML 1.0; emitted U+FFFD."
        )
    return "".join(pieces)


def read_string(element: ET.Element | None, *, rich: bool, warn: WarningSink) -> tuple[str, list[RichTextRun] | None]:
    if element is None:
        return "", None
    parts: list[str] = []
    runs: list[RichTextRun] = []
    for child in element:
        if child.tag == _NS + "t":
            value = decode_xstring(child.text or "", warn)
            parts.append(value)
            runs.append({"text": value})
        elif child.tag == _NS + "r":
            value = decode_xstring(child.findtext(_NS + "t") or "", warn)
            parts.append(value)
            item: RichTextRun = {"text": value}
            properties = child.find(_NS + "rPr") if rich else None
            if properties is not None:
                font = font_info(properties, {})
                if properties.find(_NS + "b") is not None:
                    item["bold"] = font["bold"]
                if properties.find(_NS + "i") is not None:
                    item["italic"] = font["italic"]
                if properties.find(_NS + "u") is not None:
                    item["underline"] = font["underline"]
                if color := font.get("color"):
                    item["color"] = color
            runs.append(item)
        # rPh / phoneticPr are guide/layout data, not another copy of the cell text.
    return "".join(parts), runs if rich and any(len(run) > 1 for run in runs) else None
