"""Internal HTML5 renderer orchestration and resource query helpers."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

from ..core.enums import Density
from ..core.models import DocumentManifest, ParsedDocument
from .document.pipeline import iter_plain, iter_semantic, iter_structural
from .objects.resources import render_resource, table_groups

__all__ = [
    "iter_html5",
    "manifest",
    "render_resource",
    "to_html5",
    "window",
]


def to_html5(parsed: ParsedDocument, density: Density | str = Density.SEMANTIC) -> str:
    """Return the complete markup string at the given density."""
    return "".join(iter_html5(parsed, density))


def iter_html5(parsed: ParsedDocument, density: Density | str = Density.SEMANTIC) -> Iterator[str]:
    """Yield markup chunks for streaming output."""
    resolved_density = Density.parse(density)
    if resolved_density is Density.PLAIN:
        yield from iter_plain(parsed)
    elif resolved_density is Density.STRUCTURAL:
        yield from iter_structural(parsed)
    else:
        yield from iter_semantic(parsed)


def window(
    parsed: ParsedDocument,
    page: int,
    span: int = 1,
    density: Density | str = Density.SEMANTIC,
) -> str:
    """Return content for the given page range; page=-1 means the last page."""
    resolved_density = Density.parse(density)
    if page != -1 and page < 1:
        raise ValueError("page must be -1 or greater than zero")
    if span < 1:
        raise ValueError("span must be greater than zero")
    page_index = _build_page_index(parsed)
    total_pages = max(page_index.keys()) if page_index else 1

    if page == -1:
        start_page = total_pages
    elif page < 1:
        start_page = 1
    else:
        start_page = min(page, total_pages)

    end_page = min(start_page + span - 1, total_pages)
    if page != -1 and start_page not in page_index:
        # Hole pages (multiple consecutive breaks) contain no blocks; return
        # an empty window instead of silently falling back to the whole document.
        empty_parsed = dataclasses.replace(parsed, blocks=[], headers=[], footers=[], comments=[])
        return "".join(iter_html5(empty_parsed, resolved_density))

    start_block = page_index[start_page][0]
    # When the span extends over hole pages, stop at the last block of the
    # start page instead of leaking later pages into the window.
    end_idx = page_index[end_page][1] if end_page in page_index else page_index[start_page][1]

    window_blocks = parsed.blocks[start_block : end_idx + 1]
    window_parsed = dataclasses.replace(
        parsed,
        blocks=window_blocks,
        headers=[],
        footers=[],
        comments=[],
    )
    return "".join(iter_html5(window_parsed, resolved_density))


def manifest(parsed: ParsedDocument) -> DocumentManifest:
    """Return document metadata for LLM orientation on the first call."""
    page_index = _build_page_index(parsed)
    pages = max(page_index.keys()) if page_index else 1
    return {
        "pages": pages,
        "tables": len(table_groups(parsed)),
        "images": len(parsed.assets),
        "footnotes": len(parsed.footnotes),
        "endnotes": len(parsed.endnotes),
        "comments": len(parsed.comments),
    }


def _build_page_index(parsed: ParsedDocument) -> dict[int, tuple[int, int]]:
    """Build a mapping of page number to start and end block indexes."""
    index: dict[int, tuple[int, int]] = {}
    current_page = 1
    page_start = 0

    for i, block in enumerate(parsed.blocks):
        block_page = block.get("page", 1)
        if block_page != current_page:
            index[current_page] = (page_start, i - 1)
            current_page = block_page
            page_start = i

    if parsed.blocks:
        index[current_page] = (page_start, len(parsed.blocks) - 1)
    else:
        index[1] = (0, -1)

    return index
