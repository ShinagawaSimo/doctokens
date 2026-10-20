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

    def block(item: Block) -> None:
        if item["type"] == "table":
            # Match the current DTX table projection; full rows remain available
            # through the resource API, whose global catalog is not filtered.
            for row in item["rows"][:30]:
                for cell in row["cells"]:
                    for child in cell["blocks"]:
                        block(child)
        else:
            inline(item)

    for item in document.blocks:
        block(item)
    for group in (document.headers, document.footers, document.footnotes, document.endnotes, document.comments):
        for content in group:
            inline(content)
    return used
