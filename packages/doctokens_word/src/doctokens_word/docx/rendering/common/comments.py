"""Keep selected comment definitions and their explicit conversation context."""

from __future__ import annotations

from ...model import AncillaryItem, Block, ParsedDocument
from ...model.traversal import iter_blocks, iter_runs


def window_comments(document: ParsedDocument, blocks: list[Block]) -> list[AncillaryItem]:
    selected = list(iter_blocks(blocks))
    block_ids = {block["id"] for block in selected}
    referenced = {
        item["id"]
        for block in selected
        if block["type"] != "table"
        for run in iter_runs(block.get("runs", []))
        for item in run.get("objects", [])
        if item["type"] == "commentRef" and item.get("id")
    }
    by_id = {item["id"]: item for item in document.comments if item["id"] is not None}
    keep = {key for key, item in by_id.items() if key in referenced or item.get("targetBlock") in block_ids}
    children: dict[str, list[str]] = {}
    for key, item in by_id.items():
        if parent := item.get("parentId"):
            children.setdefault(parent, []).append(key)
    pending = list(keep)
    while pending:
        key = pending.pop()
        related = list(children.get(key, []))
        if parent := by_id[key].get("parentId"):
            related.append(parent)
        for related_id in related:
            if related_id in by_id and related_id not in keep:
                keep.add(related_id)
                pending.append(related_id)
    return [item for item in document.comments if item["id"] in keep]
