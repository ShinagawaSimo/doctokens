"""Collect paragraph groups after selecting tracked paragraph-mark visibility."""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ....model import Block, ContentControl
from ....ooxml.namespaces import first_child, local_name
from ....ooxml.property_changes import retained_revision, structural_revision
from ....ooxml.wrapped_content import content_children

if TYPE_CHECKING:
    from .scanner import DocumentBodyParser

ParagraphPart = tuple[ET.Element, tuple[ContentControl, ...]]
_MARKERS = {prefix + suffix for prefix in ("moveFrom", "moveTo") for suffix in ("RangeStart", "RangeEnd")}
_IGNORED = {"tcPr", "bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd"}


def joins_next(paragraph: ET.Element, view: str) -> bool:
    mark = structural_revision(first_child(first_child(paragraph, "w", "pPr"), "w", "rPr"))
    return mark is not None and not retained_revision(mark, view)


class BlockCollector:
    def __init__(self, owner: DocumentBodyParser, part: str) -> None:
        self.owner = owner
        self.part = part
        self.blocks: list[Block] = []
        self.pending: list[ParagraphPart] = []

    def feed(self, node: ET.Element, controls: tuple[ContentControl, ...] = ()) -> None:
        name = local_name(node.tag)
        if name == "p":
            self.pending.append((node, controls))
            if not joins_next(node, str(self.owner.options.revision_mode)):
                self.flush()
        elif name in {"sdt", "sdtContent"}:
            # Expand only this structural level; table/paragraph descendants stay local.
            if name == "sdt":
                from ....ooxml.content_controls import parse_content_control

                content = first_child(node, "w", "sdtContent")
                if content is not None:
                    for child, nested in content_children(content, (*controls, parse_content_control(node))):
                        self.feed(child, nested)
            else:
                for child, nested in content_children(node, controls):
                    self.feed(child, nested)
        elif name in _MARKERS:
            if self.pending:
                self.pending.append((node, controls))
            else:
                self.owner.inline.revisions.marker(node, self.part)
        elif name in _IGNORED:
            return
        else:
            self.flush()
            if name == "tbl":
                self.blocks.extend(self.owner.parse_table(node, self.part, controls))
            elif name == "sectPr":
                self.owner._sections._collect_section_refs(node)
                self.owner._pending_page_breaks += 1
                self.owner._sections._section_break_pending = True
            else:
                self.owner._warn(
                    "UNSUPPORTED_BODY_CHILD" if self.part == "word/document.xml" else "UNSUPPORTED_STORY_CHILD",
                    f"Unsupported block container child: {name}",
                    part=self.part,
                )

    def flush(self) -> None:
        if not self.pending:
            return
        paragraphs = [item for item in self.pending if local_name(item[0].tag) == "p"]
        last = paragraphs[-1][0]
        common = paragraphs[0][1] if all(item[1] == paragraphs[0][1] for item in paragraphs) else ()
        block = self.owner.parse_paragraph(last, self.part, common, paragraph_parts=list(self.pending))
        if block is not None:
            self.blocks.append(block)
        for node, _controls in self.pending:
            node.clear()
        self.pending.clear()
