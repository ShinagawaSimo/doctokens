"""Read OMML operator properties without losing their mathematical symbols."""

from __future__ import annotations

from collections.abc import Callable
from xml.etree import ElementTree as ET

from .support import _ACCENT_MAP, _DELIM_MAP, _NARY_OPERATOR_MAP, _escape_latex, attr, child_elements, first_child

NodeConverter = Callable[[ET.Element], str]


def _property(elem: ET.Element, group: str, name: str, default: str) -> str:
    """Distinguish a missing character property from an explicitly empty one."""
    node = first_child(first_child(elem, "m", group), "m", name)
    return default if node is None else attr(node, "m", "val", "") or ""


def _content(elem: ET.Element, name: str, convert: NodeConverter) -> str:
    node = first_child(elem, "m", name)
    return convert(node) if node is not None else ""


def _hidden(elem: ET.Element, name: str) -> bool:
    node = first_child(first_child(elem, "m", "naryPr"), "m", name)
    return node is not None and (attr(node, "m", "val", "1") or "1").lower() not in {"0", "false", "off"}


def nary(elem: ET.Element, convert: NodeConverter) -> str:
    character = _property(elem, "naryPr", "chr", "∫")
    operator = _NARY_OPERATOR_MAP.get(character, _escape_latex(character))
    limits = ""
    for name, marker in (("sub", "_"), ("sup", "^")):
        value = _content(elem, name, convert)
        if value and not _hidden(elem, name + "Hide"):
            limits += f"{marker}{{{value}}}"
    # An explicitly absent operator still needs an empty base for its limits.
    prefix = operator or ("{}" if limits else "")
    return f"{prefix}{limits} {{{_content(elem, 'e', convert)}}}"


def accent(elem: ET.Element, convert: NodeConverter) -> str:
    character = _property(elem, "accPr", "chr", "̂")
    value = _content(elem, "e", convert)
    if not character:
        return value
    command = _ACCENT_MAP.get(character)
    if command is not None:
        return f"{command}{{{value}}}"
    return rf"\overset{{{_escape_latex(character)}}}{{{value}}}"


def bar(elem: ET.Element, convert: NodeConverter) -> str:
    position = _property(elem, "barPr", "pos", "bot") or "bot"
    command = r"\overline" if position == "top" else r"\underline"
    return f"{command}{{{_content(elem, 'e', convert)}}}"


def group_character(elem: ET.Element, convert: NodeConverter) -> str:
    character = _property(elem, "groupChrPr", "chr", "⏟")
    position = _property(elem, "groupChrPr", "pos", "bot") or "bot"
    value = _content(elem, "e", convert)
    if not character:
        return value
    commands = {
        ("⏞", "top"): r"\overbrace",
        ("⏟", "bot"): r"\underbrace",
        ("→", "top"): r"\overrightarrow",
        ("←", "top"): r"\overleftarrow",
        ("↔", "top"): r"\overleftrightarrow",
        ("→", "bot"): r"\underrightarrow",
        ("←", "bot"): r"\underleftarrow",
        ("↔", "bot"): r"\underleftrightarrow",
    }
    command = commands.get((character, position))
    if command is not None:
        return f"{command}{{{value}}}"
    command = r"\overset" if position == "top" else r"\underset"
    return f"{command}{{{_escape_latex(character)}}}{{{value}}}"


def delimiter(elem: ET.Element, convert: NodeConverter) -> str:
    beginning = _property(elem, "dPr", "begChr", "(")
    ending = _property(elem, "dPr", "endChr", ")")
    separator = _property(elem, "dPr", "sepChr", "|")
    # U+2502 is the standard's alternate spelling of the default separator.
    separator_text = "|" if separator == "│" else _escape_latex(separator)
    values = [convert(node) for node in child_elements(elem, "m", "e")]
    body = separator_text.join(values)
    if beginning in _DELIM_MAP or not beginning:
        left = r"\left" + (_DELIM_MAP[beginning] if beginning else ".")
    else:
        left = rf"\mathopen{{{_escape_latex(beginning)}}}"
    if ending in _DELIM_MAP or not ending:
        right = r"\right" + (_DELIM_MAP[ending] if ending else ".")
    else:
        right = rf"\mathclose{{{_escape_latex(ending)}}}"
    # A custom non-delimiter character cannot be paired with a TeX \left/\right.
    if left.startswith(r"\left") and not right.startswith(r"\right"):
        left = rf"\mathopen{{{_DELIM_MAP.get(beginning, '')}}}"
    elif right.startswith(r"\right") and not left.startswith(r"\left"):
        right = rf"\mathclose{{{_DELIM_MAP.get(ending, '')}}}"
    return f"{left} {body} {right}"
