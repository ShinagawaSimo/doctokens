"""Block-level rendering dispatcher (headings and tables only)."""

from __future__ import annotations

from collections.abc import Iterator

from ..core.models import Block, OcrStoredResult
from .inline import inline_content
from .tables import render_table


def render_block(block: Block, density: str, ocr_results: dict[str, OcrStoredResult] | None = None) -> Iterator[str]:
    """Dispatch a parsed block to its density-specific renderer."""
    if block["type"] == "heading":
        level = min(block["level"], 6)
        yield f"<h{level}>{inline_content(block, density, ocr_results)}\n"
    elif block["type"] == "paragraph":
        yield inline_content(block, density, ocr_results)
    else:
        yield from render_table(block, density, ocr_results)
