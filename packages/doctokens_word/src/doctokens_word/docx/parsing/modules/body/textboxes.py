"""Extract the existing plain reading projection of DOCX text-box content."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ....model import Block, DrawingCommon, InlineObject
from ....ooxml.numbering import NumberingState
from .containers import container_blocks
from .object_common import copy_drawing_common

if TYPE_CHECKING:
    from .scanner import DocumentBodyParser

TextboxReader = Callable[[ET.Element, str], list[Block]]


def parse_textbox_blocks(owner: DocumentBodyParser, node: ET.Element, part: str) -> list[Block]:
    from .scanner import DocumentBodyParser

    if owner._textbox_depth >= 32:
        owner._warn("TEXTBOX_NESTING_LIMIT", "Text-box nesting exceeds 32 stories", part=part)
        return []
    child = DocumentBodyParser(
        owner.package,
        owner.styles,
        owner.options,
        owner.warnings,
        owner.inline.relationships,
        owner.asset_lookup,
        owner.inline.object_lookup,
        NumberingState(owner.numbering_state.numbering, owner.warnings),
        owner.plan,
        owner.compatibility,
    )
    child.block_ids = owner.block_ids
    child.table_ids = owner.table_ids
    child._page_hint = owner._page_hint
    child._textbox_depth = owner._textbox_depth + 1
    child._anchors = owner._anchors
    child.inline.on_bookmark = owner._anchors._register_bookmark
    child.inline.on_comment_anchor = owner._anchors._register_comment_anchor
    return container_blocks(child, node, part)


def textbox_objects_from_nodes(
    nodes: list[ET.Element], common: DrawingCommon, part: str, reader: TextboxReader
) -> list[InlineObject]:
    objects: list[InlineObject] = []
    for txbx in nodes:
        blocks = reader(txbx, part)
        if not blocks:
            continue
        textbox: InlineObject = {"type": "textbox", "text": _blocks_text(blocks), "blocks": blocks}
        copy_drawing_common(textbox, common)
        objects.append(textbox)
    return objects


def _blocks_text(blocks: list[Block]) -> str:
    parts: list[str] = []
    for block in blocks:
        if block["type"] == "table":
            parts.extend("\t".join(_blocks_text(cell["blocks"]) for cell in row["cells"]) for row in block["rows"])
        else:
            parts.append(block["text"])
    return "\n".join(parts)
