"""Internal HTML5 renderer orchestration and resource query helpers."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

from ..core.enums import Density
from ..core.models import DocumentManifest, ParsedDocument
from .common.pages import iter_page_blocks
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
    total_pages = _total_pages(parsed, page_index)

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

    page_blocks = list(iter_page_blocks(parsed))
    selected_pages = set(range(start_page, end_page + 1))
    # When the span extends over hole pages, stop at the last available page
    # before the hole instead of leaking later pages into the window.
    for candidate in range(start_page, end_page + 1):
        if candidate not in page_index:
            selected_pages = set(range(start_page, candidate))
            break
    window_blocks = [block for block_page, block in page_blocks if block_page in selected_pages]
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
    pages = _total_pages(parsed, page_index)
    return {
        "pages": pages,
        "tables": len(table_groups(parsed)),
        "images": len(parsed.assets),
        "footnotes": len(parsed.footnotes),
        "endnotes": len(parsed.endnotes),
        "comments": len(parsed.comments),
    }


def _total_pages(parsed: ParsedDocument, page_index: dict[int, tuple[int, int]]) -> int:
    """Include a trailing page break even when its page has no content block."""
    indexed_pages = max(page_index.keys()) if page_index else 1
    block_end_pages = [int(block.get("pageEnd", block.get("page", 1))) for block in parsed.blocks]
    return max([indexed_pages, *block_end_pages])


def _build_page_index(parsed: ParsedDocument) -> dict[int, tuple[int, int]]:
    """Build a mapping of page number to virtual page-block indexes."""
    index: dict[int, tuple[int, int]] = {}
    current_page: int | None = None
    page_start = 0
    last_index = -1
    for i, (block_page, _block) in enumerate(iter_page_blocks(parsed)):
        last_index = i
        if block_page != current_page:
            if current_page is not None:
                index[current_page] = (page_start, i - 1)
            current_page = block_page
            page_start = i
    if current_page is not None:
        index[current_page] = (page_start, last_index)
    else:
        index[1] = (0, -1)

    return index
