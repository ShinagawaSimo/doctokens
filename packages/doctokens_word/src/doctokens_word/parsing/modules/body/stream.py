"""Stream the selected DOCX body blocks and expand block content controls."""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from doctokens_core.execution import checkpoint

from ....core.constants import _TAG_W_PARAGRAPH, _TAG_W_TABLE, first_child, local_name
from ....core.models import Block, ContentControl
from ....ooxml.content_controls import parse_content_control

if TYPE_CHECKING:
    from .scanner import DocumentBodyParser


def read_blocks(owner: DocumentBodyParser) -> list[Block]:
    """Dispatch complete body children from the normalized XML event stream."""
    blocks: list[Block] = []
    with owner.package.open_entry("word/document.xml") as stream:
        parser = owner.compatibility.iter_events(stream, "word/document.xml")
        stack: list[str] = []
        body_depth: int | None = None
        measured = 0
        for event, elem in parser:
            # Optimization: use local_name to avoid split memory allocation.
            lname = local_name(elem.tag)
            if event == "start":
                # start events only maintain the position stack; they don't build a full DOM.
                stack.append(lname)
                if lname == "body":
                    body_depth = len(stack)
                continue

            direct_body_child = (
                body_depth is not None and len(stack) == body_depth + 1 and len(stack) >= 2 and stack[-2] == "body"
            )
            if direct_body_child:
                checkpoint("reading DOCX body")
            if direct_body_child and lname == "p":
                # Only handle paragraphs that are direct children of body, so table cell content is not hoisted twice.
                block = owner.parse_paragraph(elem, "word/document.xml")
                if block is not None:
                    blocks.append(block)
                elem.clear()
            elif direct_body_child and lname == "tbl":
                # Tables can contain page breaks, so parse_table returns a list (one sub-table block per page).
                blocks.extend(owner.parse_table(elem, "word/document.xml"))
                elem.clear()
            elif direct_body_child and lname == "sectPr":
                # Section break: Word always starts a new section on a new page when rendering.
                owner._sections._collect_section_refs(elem)
                owner._pending_page_breaks += 1
                owner._sections._section_break_pending = True
                elem.clear()
            elif direct_body_child and lname == "sdt":
                # Content controls wrap content (e.g. whole documents from
                # template tools); parse their w:sdtContent children.
                _parse_sdt(owner, elem, blocks)
                elem.clear()
            elif direct_body_child and lname not in {
                "bookmarkStart",
                "bookmarkEnd",
                "proofErr",
                "permStart",
                "permEnd",
            }:
                # Content-bearing wrappers we do not support must not be
                # dropped silently.
                owner._warn(
                    "UNSUPPORTED_BODY_CHILD",
                    f"Unsupported body-level element: {lname}",
                    part="word/document.xml",
                )
                elem.clear()

            if lname == "body":
                body_depth = None
            if owner.package.memory_budget is not None and len(blocks) > measured:
                owner.package.memory_budget.add_fragment(blocks[measured:])
                measured = len(blocks)
            stack.pop()
    return blocks


def _parse_sdt(
    owner: DocumentBodyParser,
    sdt: ET.Element,
    blocks: list[Block],
    parent_controls: tuple[ContentControl, ...] = (),
) -> None:
    """Parse a content control while preserving its metadata on its blocks."""
    controls = (*parent_controls, parse_content_control(sdt))
    content = first_child(sdt, "w", "sdtContent")
    if content is None:
        return
    for child in content:
        child_tag = child.tag
        if child_tag == _TAG_W_PARAGRAPH:
            block = owner.parse_paragraph(child, "word/document.xml", controls)
            if block is not None:
                blocks.append(block)
        elif child_tag == _TAG_W_TABLE:
            blocks.extend(owner.parse_table(child, "word/document.xml", controls))
        elif local_name(child_tag) == "sdt":
            _parse_sdt(owner, child, blocks, controls)
