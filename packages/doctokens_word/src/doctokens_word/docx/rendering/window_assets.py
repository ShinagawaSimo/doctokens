"""Project window image declarations without renumbering package resources."""

from __future__ import annotations

from ..model import AncillaryItem, Block, InlineContainer, ParsedDocument
from ..model.traversal import iter_runs
from .common.constants import _TABLE_TRUNCATE_DTX, _TABLE_TRUNCATE_PLAIN
from .plain.helpers import collect_refs


def referenced_image_ids(document: ParsedDocument, density: str = "semantic") -> set[str]:
    used: set[str] = set()

    def inline(container: InlineContainer) -> None:
        for run in iter_runs(container.get("runs", [])):
            for item in run.get("objects", []):
                if item["type"] == "image" and item.get("assetId"):
                    used.add(item["assetId"])
                for child in item.get("blocks", []):
                    block(child)

    def block(item: Block, *, nested_table: bool = False) -> None:
        if item["type"] == "table":
            # Match the current DTX table projection; full rows remain available
            # through the resource API, whose global catalog is not filtered.
            rows = item["rows"]
            if density == "plain" and len(rows) > _TABLE_TRUNCATE_PLAIN:
                rows = rows[:1]
            elif density != "plain" and not nested_table and len(rows) > _TABLE_TRUNCATE_DTX:
                rows = rows[:2]
            for row in rows:
                for cell in row["cells"]:
                    for child in cell["blocks"]:
                        block(child, nested_table=child["type"] == "table")
        else:
            inline(item)

    for item in document.blocks:
        block(item)
    groups: tuple[list[AncillaryItem], ...]
    if density == "plain":
        footnotes = {key for item in document.blocks if item["type"] != "table" for key in collect_refs(item, "footnoteRef")}
        endnotes = {key for item in document.blocks if item["type"] != "table" for key in collect_refs(item, "endnoteRef")}
        groups = (
            [item for item in document.footnotes if item.get("id") in footnotes],
            [item for item in document.endnotes if item.get("id") in endnotes],
            document.comments,
        )
    else:
        groups = (document.footnotes, document.endnotes, document.comments)
    if density == "semantic":
        groups = (*groups, document.headers, document.footers)
    for group in groups:
        for content in group:
            inline(content)
    return used
