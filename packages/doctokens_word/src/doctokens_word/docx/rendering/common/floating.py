"""Keep anchored text-box stories separate without losing source page selection."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from doctokens_core.runtime.execution import checkpoint

from ...model import Block, InlineContainer, InlineObject, ParsedDocument, Run
from .pages import iter_block_page_segments


def is_floating_textbox(item: InlineObject) -> bool:
    return item["type"] == "textbox" and item.get("placement") == "anchor" and bool(item.get("id"))


def floating_textboxes(container: InlineContainer) -> list[InlineObject]:
    return [item for run in container.get("runs", []) for item in run.get("objects", []) if is_floating_textbox(item)]


def iter_flow_page_blocks(document: ParsedDocument) -> Iterator[tuple[int, Block]]:
    """Rejoin selected fragments of an anchored story before rendering its prose."""
    index = 0
    while index < len(document.blocks):
        checkpoint("rendering DOCX blocks")
        block = document.blocks[index]
        index += 1
        if block["type"] == "table":
            yield block.get("page", 1), block
            continue
        group = [block]
        while index < len(document.blocks):
            following = document.blocks[index]
            if following["type"] == "table" or (following["part"], following["id"]) != (block["part"], block["id"]):
                break
            group.append(following)
            index += 1
        if not any(floating_textboxes(cast(InlineContainer, item)) for item in group):
            for item in group:
                yield from iter_block_page_segments(item)
            continue
        if len(group) > 1:
            combined = dict(block)
            runs: list[Run] = []
            current_page = block["page"]
            for item in group:
                runs.extend({"text": "", "pageBreak": True} for _ in range(current_page, item["page"]))
                runs.extend(item.get("runs", []))
                current_page = item.get("pageEnd", item["page"])
            combined["runs"] = runs
            combined["text"] = "".join(run["text"] for run in runs)
            combined["pageEnd"] = current_page
            block = cast(Block, combined)
        yield block["page"], block
