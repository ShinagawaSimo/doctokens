"""Expand content controls and transparent OOXML containers at a chosen structural level."""

from __future__ import annotations

from collections.abc import Iterator
from xml.etree import ElementTree as ET

from ..model import ContentControl
from .content_controls import parse_content_control
from .namespaces import first_child, local_name


def content_children(
    parent: ET.Element, controls: tuple[ContentControl, ...] = ()
) -> Iterator[tuple[ET.Element, tuple[ContentControl, ...]]]:
    for child in parent:
        name = local_name(child.tag)
        if name == "sdt":
            content = first_child(child, "w", "sdtContent")
            if content is not None:
                yield from content_children(content, (*controls, parse_content_control(child)))
        elif name in {"sdtContent", "customXml", "smartTag"}:
            yield from content_children(child, controls)
        else:
            yield child, controls
