"""Extract the existing plain reading projection of DOCX text-box content."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ....core.constants import child_elements, local_name
from ....core.models import DrawingCommon, InlineObject
from .object_common import copy_drawing_common


def textbox_objects_from_nodes(nodes: list[ET.Element], common: DrawingCommon) -> list[InlineObject]:
    objects: list[InlineObject] = []
    for txbx in nodes:
        text = _container_plain_text(txbx)
        if text.strip():
            textbox: InlineObject = {"type": "textbox", "text": text}
            copy_drawing_common(textbox, common)
            objects.append(textbox)
    return objects


def _container_plain_text(node: ET.Element) -> str:
    parts: list[str] = []
    for child in node:
        lname = local_name(child.tag)
        if lname == "p":
            text = _inline_plain_text(child)
        elif lname == "tbl":
            text = _table_plain_text(child)
        else:
            text = _inline_plain_text(child)
        if text.strip():
            parts.append(text)
    return "\n".join(parts)


def _table_plain_text(tbl: ET.Element) -> str:
    rows: list[str] = []
    for tr in child_elements(tbl, "w", "tr"):
        cells = [_container_plain_text(tc) for tc in child_elements(tr, "w", "tc")]
        row = " | ".join(cell.strip() for cell in cells if cell.strip())
        if row:
            rows.append(row)
    return "\n".join(rows)


def _inline_plain_text(node: ET.Element) -> str:
    parts: list[str] = []
    for item in node.iter():
        lname = local_name(item.tag)
        if lname == "t":
            parts.append(item.text or "")
        elif lname == "tab":
            parts.append("\t")
        elif lname in {"br", "cr"}:
            parts.append("\n")
    return "".join(parts)
