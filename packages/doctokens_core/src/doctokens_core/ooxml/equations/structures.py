"""Reading projections for fractions, roots, visibility and enclosure marks."""

from __future__ import annotations

from collections.abc import Callable
from xml.etree import ElementTree as ET

from .support import _wrap_group, attr, first_child
from .text import flag

NodeConverter = Callable[[ET.Element], str]


def argument(node: ET.Element, name: str, convert: NodeConverter) -> str:
    child = first_child(node, "m", name)
    return convert(child) if child is not None else ""


def fraction(node: ET.Element, convert: NodeConverter) -> str:
    numerator = argument(node, "num", convert)
    denominator = argument(node, "den", convert)
    kind = first_child(first_child(node, "m", "fPr"), "m", "type")
    if kind is not None and attr(kind, "m", "val") == "noBar":
        return rf"\genfrac{{}}{{}}{{0pt}}{{}}{{{numerator}}}{{{denominator}}}"
    return rf"\frac{{{numerator}}}{{{denominator}}}"


def radical(node: ET.Element, convert: NodeConverter) -> str:
    degree = "" if flag(first_child(node, "m", "radPr"), "degHide") else argument(node, "deg", convert)
    value = argument(node, "e", convert)
    return rf"\sqrt[{degree}]{{{value}}}" if degree else rf"\sqrt{{{value}}}"


def phantom(node: ET.Element, convert: NodeConverter) -> str:
    value = argument(node, "e", convert)
    return value if flag(first_child(node, "m", "phantPr"), "show", True) else rf"\phantom{{{value}}}"


def border_box(node: ET.Element, convert: NodeConverter) -> str:
    value = argument(node, "e", convert)
    properties = first_child(node, "m", "borderBoxPr")
    visible = {edge for edge in ("Top", "Bot", "Left", "Right") if not flag(properties, "hide" + edge)}
    if len(visible) == 4:
        value = rf"\boxed{{{value}}}"
    else:
        if "Top" in visible:
            value = rf"\overline{{{value}}}"
        if "Bot" in visible:
            value = rf"\underline{{{value}}}"
        if visible & {"Left", "Right"}:
            left = r"\lvert" if "Left" in visible else "."
            right = r"\rvert" if "Right" in visible else "."
            value = rf"\left{left} {value} \right{right}"
    forward = flag(properties, "strikeBLTR")
    backward = flag(properties, "strikeTLBR")
    if forward or backward:
        command = r"\xcancel" if forward and backward else r"\cancel" if forward else r"\bcancel"
        value = f"{command}{{{value}}}"
    # Reading annotations retain these source line states without inventing a
    # diagonal cancellation or guessed coordinates.
    for name, label in (("strikeH", "horizontal strike"), ("strikeV", "vertical strike")):
        if flag(properties, name):
            value = rf"\overset{{\text{{{label}}}}}{{{value}}}"
    return value


def script(node: ET.Element, kind: str, convert: NodeConverter) -> str:
    value = _wrap_group(argument(node, "e", convert))
    base = value if kind == "sPre" else ""
    if kind == "sPre":
        value = "{}"
    for name, marker in (("sub", "_"), ("sup", "^")):
        part = argument(node, name, convert)
        if part:
            value += f"{marker}{{{part}}}"
    return value + base
