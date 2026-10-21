"""Anchors."""

from __future__ import annotations

from typing import cast

from ....core.models import (
    Block,
    TextBlock,
)
from ....core.traversal import iter_blocks


class BlockIdAllocator:
    """Assign stable internal IDs to body blocks."""

    def __init__(self, prefix: str = "b") -> None:
        self._next = 1
        self._prefix = prefix

    def allocate(self) -> str:
        # Count independently per document to avoid shared state across concurrent parses.
        block_id = f"{self._prefix}{self._next}"
        self._next += 1
        return block_id


class BodyAnchors:
    """Track document bookmarks and the first visible anchors of comments."""

    def __init__(self) -> None:
        self._comment_anchors: dict[str, str] = {}
        self._bookmarks_by_block: dict[str, list[str]] = {}

    def _register_bookmark(self, name: str, block_id: str) -> None:
        """Register a bookmark while its enclosing paragraph still has a stable block ID."""
        anchors = self._bookmarks_by_block.setdefault(block_id, [])
        if name not in anchors:
            anchors.append(name)

    def _register_comment_anchor(self, comment_id: str, block_id: str) -> None:
        """Keep the first visible block for a Word comment range/reference."""
        self._comment_anchors.setdefault(comment_id, block_id)

    @staticmethod
    def _discard_unreferenced_anchors(blocks: list[Block]) -> None:
        """Avoid carrying bookmarks that are never a parsed internal-navigation target."""
        anchored_blocks: list[TextBlock] = []
        used: set[str] = set()

        def visit(items: list[Block]) -> None:
            for item in iter_blocks(items):
                if item["type"] in {"paragraph", "heading"}:
                    if item.get("anchors"):
                        anchored_blocks.append(item)
                    for run in item.get("runs", []):
                        link = run.get("link")
                        if link and link.get("anchor"):
                            used.add(link["anchor"])

        visit(blocks)
        for item in anchored_blocks:
            anchors = [anchor for anchor in item.get("anchors", []) if anchor in used]
            if anchors:
                item["anchors"] = anchors
            else:
                cast(dict[str, object], item).pop("anchors", None)
