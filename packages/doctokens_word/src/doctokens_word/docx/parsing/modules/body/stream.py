"""Stream selected body blocks while retaining paragraphs that lose their mark."""

from __future__ import annotations

from typing import TYPE_CHECKING

from doctokens_core.runtime.execution import checkpoint

from ....model import Block
from ....ooxml.namespaces import local_name
from .paragraph_groups import BlockCollector

if TYPE_CHECKING:
    from .scanner import DocumentBodyParser


def read_blocks(owner: DocumentBodyParser) -> list[Block]:
    collector = BlockCollector(owner, "word/document.xml")
    measured = 0
    depth = 0
    body_depth: int | None = None
    with owner.package.open_entry("word/document.xml") as stream:
        for event, node in owner.compatibility.iter_events(stream, "word/document.xml"):
            name = local_name(node.tag)
            if event == "start":
                depth += 1
                if name == "body":
                    body_depth = depth
                continue
            if body_depth is not None and depth == body_depth + 1:
                checkpoint("reading DOCX body")
                collector.feed(node)
                if not (collector.pending and collector.pending[-1][0] is node):
                    node.clear()
            if name == "body":
                collector.flush()
                body_depth = None
            if owner.package.memory_budget is not None and len(collector.blocks) > measured:
                owner.package.memory_budget.add_fragment(collector.blocks[measured:])
                measured = len(collector.blocks)
            depth -= 1
    return collector.blocks
