"""Project window image declarations without renumbering package resources."""

from __future__ import annotations

from ..core.models import Block, InlineContainer, ParsedDocument


def referenced_image_ids(document: ParsedDocument) -> set[str]:
    used: set[str] = set()

    def inline(container: InlineContainer) -> None:
        for run in container.get("runs", []):
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
            for row in rows[:2] if not nested_table and len(rows) > 30 else rows:
                for cell in row["cells"]:
                    for child in cell["blocks"]:
                        block(child, nested_table=child["type"] == "table")
        else:
            inline(item)

    for item in document.blocks:
        block(item)
    for group in (document.headers, document.footers, document.footnotes, document.endnotes, document.comments):
        for content in group:
            inline(content)
    return used
