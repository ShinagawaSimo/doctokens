"""Read story/table-cell block containers without sharing inline field state."""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ....model import Block, ContentControl
from ....ooxml.content_controls import parse_content_control
from ....ooxml.namespaces import first_child, qualified_name

if TYPE_CHECKING:
    from .scanner import DocumentBodyParser


def container_blocks(
    owner: DocumentBodyParser, node: ET.Element, part: str, controls: tuple[ContentControl, ...] = ()
) -> list[Block]:
    blocks: list[Block] = []
    for child in node:
        if owner.inline.revisions.marker(child, part):
            continue
        if child.tag == qualified_name("w", "p"):
            block = owner.parse_paragraph(child, part, controls)
            if block is not None:
                blocks.append(block)
        elif child.tag == qualified_name("w", "tbl"):
            blocks.extend(owner.parse_table(child, part, controls))
        elif child.tag == qualified_name("w", "sdt"):
            content = first_child(child, "w", "sdtContent")
            if content is not None:
                blocks.extend(container_blocks(owner, content, part, (*controls, parse_content_control(child))))
        elif child.tag not in {
            qualified_name("w", name) for name in ("tcPr", "bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd")
        }:
            owner._warn("UNSUPPORTED_STORY_CHILD", "Unsupported block container child: " + child.tag, part=part)
    return blocks
