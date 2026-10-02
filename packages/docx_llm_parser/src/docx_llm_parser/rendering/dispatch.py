"""Internal output orchestration and resource query helpers."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

from ..core.enums import Density
from ..core.models import DocumentManifest, ParsedDocument
from .common.pages import iter_page_blocks
from .objects.resources import render_resource, table_groups

__all__ = [
    "build_manifest",
    "iter_output",
    "render_page_window",
    "render_resource",
    "to_output",
]


def to_output(parsed_document: ParsedDocument, density: Density | str = Density.SEMANTIC) -> str:
    """Return the complete self-defined output string at the given density."""
    return "".join(iter_output(parsed_document, density))


def iter_output(parsed_document: ParsedDocument, density: Density | str = Density.SEMANTIC) -> Iterator[str]:
    """Yield self-defined output chunks at the requested density."""
    from ..parsing import get_render_pipeline

    yield from get_render_pipeline(Density.parse(density)).render(parsed_document)


def render_page_window(
    parsed_document: ParsedDocument,
    page: int,
    span: int = 1,
    density: Density | str = Density.SEMANTIC,
) -> str:
    """Return output for the given page range; page=-1 means the last page."""
    resolved_density = Density.parse(density)
    if page != -1 and page < 1:
        raise ValueError("page must be -1 or greater than zero")
    if span < 1:
        raise ValueError("span must be greater than zero")
    page_index = _build_page_index(parsed_document)
    total_pages = _total_pages(parsed_document, page_index)

    if page == -1:
        start_page = total_pages
    elif page > total_pages:
        empty_document = dataclasses.replace(parsed_document, blocks=[], headers=[], footers=[], comments=[])
        return "".join(iter_output(empty_document, resolved_density))
    else:
        start_page = page

    end_page = min(start_page + span - 1, total_pages)
    if page != -1 and start_page not in page_index:
        # Hole pages (multiple consecutive breaks) contain no blocks; return
        # an empty window instead of silently falling back to the whole document.
        empty_document = dataclasses.replace(parsed_document, blocks=[], headers=[], footers=[], comments=[])
        return "".join(iter_output(empty_document, resolved_density))

    page_blocks = list(iter_page_blocks(parsed_document))
    selected_pages = set(range(start_page, end_page + 1))
    # When the span extends over hole pages, stop at the last available page
    # before the hole instead of leaking later pages into the window.
    for candidate in range(start_page, end_page + 1):
        if candidate not in page_index:
            selected_pages = set(range(start_page, candidate))
            break
    selected_blocks = [block for block_page, block in page_blocks if block_page in selected_pages]
    selected_document = dataclasses.replace(
        parsed_document,
        blocks=selected_blocks,
        headers=[],
        footers=[],
        comments=[],
    )
    return "".join(iter_output(selected_document, resolved_density))


def build_manifest(parsed_document: ParsedDocument) -> DocumentManifest:
    """Build document metadata for LLM orientation on the first call."""
    page_index = _build_page_index(parsed_document)
    pages = _total_pages(parsed_document, page_index)
    return {
        "pages": pages,
        "tables": len(table_groups(parsed_document)),
        "images": len(parsed_document.assets),
        "footnotes": len(parsed_document.footnotes),
        "endnotes": len(parsed_document.endnotes),
        "comments": len(parsed_document.comments),
    }


def describe_pages(parsed_document: ParsedDocument) -> dict[str, object]:
    index = _build_page_index(parsed_document)
    return {
        "kind": "saved-page-hints",
        "page_count": _total_pages(parsed_document, index),
        "content_pages": [page for page, (start, end) in index.items() if end >= start],
    }


def _total_pages(parsed_document: ParsedDocument, page_index: dict[int, tuple[int, int]]) -> int:
    """Include a trailing page break even when its page has no content block."""
    indexed_pages = max(page_index.keys()) if page_index else 1
    block_end_pages = [int(block.get("pageEnd", block.get("page", 1))) for block in parsed_document.blocks]
    return max([indexed_pages, *block_end_pages])


def _build_page_index(parsed_document: ParsedDocument) -> dict[int, tuple[int, int]]:
    """Build a mapping of page number to virtual page-block indexes."""
    page_block_index: dict[int, tuple[int, int]] = {}
    current_page: int | None = None
    page_start = 0
    last_index = -1
    for block_index, (block_page, _block) in enumerate(iter_page_blocks(parsed_document)):
        last_index = block_index
        if block_page != current_page:
            if current_page is not None:
                page_block_index[current_page] = (page_start, block_index - 1)
            current_page = block_page
            page_start = block_index
    if current_page is not None:
        page_block_index[current_page] = (page_start, last_index)
    else:
        page_block_index[1] = (0, -1)

    return page_block_index
