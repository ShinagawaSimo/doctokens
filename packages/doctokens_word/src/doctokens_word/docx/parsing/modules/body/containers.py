"""Read cell/text-box stories with local paragraph-mark projection."""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ....model import Block, ContentControl
from .paragraph_groups import BlockCollector

if TYPE_CHECKING:
    from .scanner import DocumentBodyParser


def container_blocks(
    owner: DocumentBodyParser, node: ET.Element, part: str, controls: tuple[ContentControl, ...] = ()
) -> list[Block]:
    collector = BlockCollector(owner, part)
    for child in node:
        collector.feed(child, controls)
    collector.flush()
    return collector.blocks
