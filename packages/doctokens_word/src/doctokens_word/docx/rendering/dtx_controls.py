"""Project complete control content after grouping its adjacent source fragments."""

from __future__ import annotations

from collections.abc import Sequence
from xml.etree import ElementTree as ET

from doctokens_core.output.xml import append, text

from ..model import ContentControl


class _ControlElement(ET.Element):
    """Keep occurrence identity in memory, never in serialized attributes."""

    def __init__(self, control: ContentControl, density: str) -> None:
        self.control = control
        self.semantic = density == "semantic"
        attrs: dict[str, str] = {}
        if label := control.get("label"):
            attrs["label"] = label
        if self.semantic:
            if control.get("controlType", "unknown") != "unknown":
                attrs["type"] = control["controlType"]
            if lock := control.get("lock"):
                attrs["lock"] = lock
        super().__init__("content-control", dict(sorted(attrs.items())))


def append_controls(parent: ET.Element, controls: Sequence[ContentControl], density: str) -> ET.Element:
    for control in controls:
        child = _ControlElement(control, density)
        parent.append(child)
        parent = child
    return parent


def finish_controls(parent: ET.Element) -> None:
    """Group one occurrence before selecting choices and removing redundant p."""
    previous: ET.Element | None = None
    for child in list(parent):
        if (
            isinstance(child, _ControlElement)
            and isinstance(previous, _ControlElement)
            and child.control is previous.control
            and child.semantic == previous.semantic
            and not previous.tail
        ):
            text(previous, child.text or "")
            previous.extend(child)
            previous.tail = child.tail
            parent.remove(child)
        else:
            previous = child
    for child in parent:
        finish_controls(child)
    if not isinstance(parent, _ControlElement):
        return
    if not parent.semantic:
        _empty_checkbox_value(parent)
        return
    _flatten_paragraph(parent)
    kind = parent.control.get("controlType")
    if kind == "checkbox":
        value = ET.Element("value")
        _move_content(parent, value)
        choice = append(parent, "choice", checked=parent.control.get("checked"))
        _move_content(value, choice)
    elif kind in {"dropDownList", "comboBox"}:
        _append_choices(parent, kind)


def _flatten_paragraph(node: ET.Element) -> None:
    if not node.text and len(node) == 1 and node[0].tag == "p" and not node[0].attrib:
        paragraph = node[0]
        node.remove(paragraph)
        _move_content(paragraph, node)
        text(node, paragraph.tail or "")


def _move_content(source: ET.Element, target: ET.Element) -> None:
    text(target, source.text or "")
    source.text = None
    for child in list(source):
        source.remove(child)
        target.append(child)


def _reading_text(node: ET.Element) -> str:
    if node.tag == "br":
        return "\n"
    if node.tag == "tab":
        return "\t"
    return (node.text or "") + "".join(_reading_text(child) + (child.tail or "") for child in node)


def _append_choices(node: _ControlElement, kind: str) -> None:
    options = node.control.get("options", [])
    current = _reading_text(node)
    # Unexpected multi-block/object content stays readable, without guessing a
    # selected candidate from the text concatenation of a table or nested control.
    complex_content = (
        any(
            child.tag in {"table", "nested-table", "content-control", "img", "textbox", "equation", "page"}
            or child.tag.startswith("h")
            for child in node.iter()
            if child is not node
        )
        or sum(child.tag == "p" for child in node) > 1
    )
    if complex_content:
        for option in options:
            append(node, "choice", option)
        return
    value = ET.Element("value")
    _move_content(node, value)
    selected = options.index(current) if current in options else None
    for index, option in enumerate(options):
        choice = append(node, "choice", checked=True if index == selected else None)
        if index == selected:
            _move_content(value, choice)
        else:
            choice.text = option
    if selected is None and (current or len(value)):
        if kind == "comboBox":
            choice = append(node, "choice", checked=True, listed=False)
            _move_content(value, choice)
        else:
            # A saved prompt or unmatched display is not a declared selection.
            node.insert(0, value)


def _empty_checkbox_value(node: _ControlElement) -> None:
    if "checked" not in node.control or _reading_text(node):
        return
    if any(child.tag != "p" for child in node.iter() if child is not node):
        return
    value = "checked" if node.control["checked"] else "unchecked"
    if len(node):
        node[0].text = value
    else:
        node.text = value
