"""Page-aware iteration over DOCX body blocks."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from ...core.models import Block, ParsedDocument
from .text import split_runs_at_page_breaks


def iter_page_blocks(parsed_document: ParsedDocument) -> Iterator[tuple[int, Block]]:
    """Yield top-level blocks split at inline calculated page breaks."""
    for block in parsed_document.blocks:
        if block["type"] in {"paragraph", "heading"}:
            yield from iter_block_page_segments(block)
        else:
            yield int(block.get("page", 1)), block


def iter_block_page_segments(block: Block) -> Iterator[tuple[int, Block]]:
    """Yield one paragraph/heading fragment for each non-empty page segment."""
    page = block.get("page", 1)
    if block["type"] not in {"paragraph", "heading"}:
        yield page, block
        return
    if "runs" not in block:
        page_segment_records = block.get("pageSegments")
        if not isinstance(page_segment_records, list):
            yield page, block
            return
        for page_segment in page_segment_records:
            if not isinstance(page_segment, dict) or not page_segment.get("text"):
                continue
            page_fragment = dict(block)
            segment_page = cast(int, page_segment.get("page", page))
            page_fragment["page"] = segment_page
            page_fragment["text"] = str(page_segment.get("text", ""))
            page_fragment.pop("pageSegments", None)
            page_fragment.pop("pageEnd", None)
            yield segment_page, cast(Block, page_fragment)
        return

    run_segments = split_runs_at_page_breaks(block["runs"])
    leading_empty_segments = 0
    for segment in run_segments:
        if any(run["text"] or run.get("objects") for run in segment) or block.get("contentControls"):
            break
        leading_empty_segments += 1
    physical_page = page - leading_empty_segments
    for segment_index, segment_runs in enumerate(run_segments):
        if not any(run["text"] or run.get("objects") for run in segment_runs) and not block.get("contentControls"):
            continue
        page_fragment = dict(block)
        page_fragment["page"] = physical_page + segment_index
        page_fragment["runs"] = segment_runs
        page_fragment["text"] = "".join(run["text"] for run in segment_runs)
        page_fragment.pop("pageEnd", None)
        yield physical_page + segment_index, cast(Block, page_fragment)
