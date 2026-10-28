"""Math-run text, encoded alphabets and deterministic Word symbol characters."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from xml.etree import ElementTree as ET

from ..symbols import symbol_character
from .support import _escape_latex, attr, first_child

HARD_BREAK = "\x00br\x00"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
WarningSink = Callable[[str, str], None]


def flag(properties: ET.Element | None, name: str, default: bool = False) -> bool:
    node = first_child(properties, "m", name)
    if node is None:
        return default
    return (attr(node, "m", "val", "1") or "1").lower() not in {"0", "false", "off"}


_LETTERLIKE = {
    "SCRIPT CAPITAL B": "ℬ",
    "SCRIPT CAPITAL E": "ℰ",
    "SCRIPT CAPITAL F": "ℱ",
    "SCRIPT CAPITAL H": "ℋ",
    "SCRIPT CAPITAL I": "ℐ",
    "SCRIPT CAPITAL L": "ℒ",
    "SCRIPT CAPITAL M": "ℳ",
    "SCRIPT CAPITAL R": "ℛ",
    "SCRIPT SMALL E": "ℯ",
    "SCRIPT SMALL G": "ℊ",
    "SCRIPT SMALL O": "ℴ",
    "FRAKTUR CAPITAL C": "ℭ",
    "FRAKTUR CAPITAL H": "ℌ",
    "FRAKTUR CAPITAL I": "ℑ",
    "FRAKTUR CAPITAL R": "ℜ",
    "FRAKTUR CAPITAL Z": "ℨ",
    "DOUBLE-STRUCK CAPITAL C": "ℂ",
    "DOUBLE-STRUCK CAPITAL H": "ℍ",
    "DOUBLE-STRUCK CAPITAL N": "ℕ",
    "DOUBLE-STRUCK CAPITAL P": "ℙ",
    "DOUBLE-STRUCK CAPITAL Q": "ℚ",
    "DOUBLE-STRUCK CAPITAL R": "ℝ",
    "DOUBLE-STRUCK CAPITAL Z": "ℤ",
}


def alphabet(value: str, properties: ET.Element | None, warn: WarningSink) -> str:
    """Decode mathematical letter identities; leave operators and Unicode intact."""
    script_node = first_child(properties, "m", "scr")
    style_node = first_child(properties, "m", "sty")
    script = attr(script_node, "m", "val", "roman") if script_node is not None else "roman"
    style = attr(style_node, "m", "val", "i") if style_node is not None else "i"
    if script == "roman":
        escaped = _escape_latex(value)
        commands = {"p": r"\mathrm", "b": r"\mathbf", "i": r"\mathit", "bi": r"\boldsymbol"}
        if style_node is None:
            return escaped
        if style not in commands:
            warn("MATH_STYLE_UNSUPPORTED", f"Unsupported mathematical style: {style}")
            return escaped
        return f"{commands[style]}{{{escaped}}}"
    bold = style in {"b", "bi"}
    prefixes = {
        "script": "BOLD SCRIPT" if bold else "SCRIPT",
        "fraktur": "BOLD FRAKTUR" if bold else "FRAKTUR",
        "double-struck": "DOUBLE-STRUCK",
        "monospace": "MONOSPACE",
        "sans-serif": "SANS-SERIF" + (" BOLD" if bold else "") + (" ITALIC" if style in {"i", "bi"} else ""),
    }
    prefix = prefixes.get(script or "")
    if prefix is None:
        warn("MATH_SCRIPT_UNSUPPORTED", f"Unsupported mathematical alphabet: {script}")
        return _escape_latex(value)
    converted: list[str] = []
    for char in value:
        if char.isascii() and char.isalpha():
            suffix = ("CAPITAL " if char.isupper() else "SMALL ") + char.upper()
        elif char.isascii() and char.isdigit():
            suffix = "DIGIT " + unicodedata.name(char).removeprefix("DIGIT ")
        else:
            converted.append(char)
            continue
        name = prefix + " " + suffix
        converted.append(unicodedata.lookup("MATHEMATICAL " + name) if _has_name(name) else _LETTERLIKE.get(name, char))
    return _escape_latex("".join(converted))


def _has_name(name: str) -> bool:
    try:
        unicodedata.lookup("MATHEMATICAL " + name)
    except KeyError:
        return False
    return True


def word_character(node: ET.Element, warn: WarningSink) -> str:
    if node.tag == _W + "noBreakHyphen":
        return r"\text{-}"
    if node.tag == _W + "softHyphen":
        # A discretionary glyph needs line layout and is invisible in an
        # unbroken reading expression.
        return ""
    if node.tag == _W + "tab":
        return r"\quad "
    if node.tag in {_W + "br", _W + "cr"}:
        return HARD_BREAK
    if node.tag == _W + "sym":
        font = attr(node, "w", "font", "") or ""
        try:
            code = int(attr(node, "w", "char", "") or "", 16)
        except ValueError:
            code = -1
        character = symbol_character(font, code)
        if character is not None:
            return _escape_latex(character)
        warn("MATH_SYMBOL_UNSUPPORTED", f"Cannot decode mathematical symbol in font {font!r}")
        return ""
    if node.tag in {_W + "rPr", _W + "fldChar", _W + "instrText", _W + "delInstrText", _W + "lastRenderedPageBreak"}:
        return ""
    warn("MATH_RUN_CHILD_UNSUPPORTED", f"Unsupported mathematical run content: {node.tag}")
    return ""


def run_text(node: ET.Element, escape_math: Callable[[str], str], warn: WarningSink, *, alignment: bool = False) -> str:
    properties = first_child(node, "m", "rPr")
    normal = flag(properties, "nor")
    pieces: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        value = "".join(pending)
        pending.clear()
        if not value:
            return
        values = value.split("&") if alignment and not normal else [value]
        for index, segment in enumerate(values):
            if index:
                pieces.append(escape_math("&"))
            if normal:
                pieces.append(r"\text{" + _escape_latex(segment) + "}")
            elif first_child(properties, "m", "scr") is not None or first_child(properties, "m", "sty") is not None:
                if segment:
                    pieces.append(alphabet(segment, properties, warn))
            else:
                pieces.append(escape_math(segment))

    for child in node:
        if child.tag == _M + "rPr":
            continue
        if child.tag in {_M + "t", _W + "t", _W + "delText"}:
            pending.append(child.text or "")
        else:
            flush()
            pieces.append(word_character(child, warn))
    flush()
    return "".join(pieces)
