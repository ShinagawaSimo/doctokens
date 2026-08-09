"""Internal HTML5 renderer orchestration and resource query helpers."""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Iterator
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter

from ..core.enums import Density
from ..core.models import DocumentManifest, ParsedDocument
from ._metrics import record_render_metrics, write_metrics_debug
from ._render import iter_l0, iter_l1, iter_l2
from .resources import render_resource, table_groups

__all__ = [
    "iter_html5",
    "manifest",
    "render_resource",
    "to_html5",
    "window",
    "write_outputs",
]


def write_outputs(
    parsed: ParsedDocument,
    output_dir: Path,
    density: Density | str = Density.SEMANTIC,
) -> dict[str, str]:
    """Write the final markup file and record render timing in metrics."""
    resolved_density = Density.parse(density)
    output_dir.mkdir(parents=True, exist_ok=True)
    density_files = {
        Density.PLAIN: "l0.txt",
        Density.STRUCTURAL: "l1.html",
        Density.SEMANTIC: "parsed.html",
    }
    fname = density_files[resolved_density]
    output_path = output_dir / fname
    start = perf_counter()
    output_chars = 0
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=output_dir,
            prefix=f".{fname}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            for chunk in iter_html5(parsed, resolved_density):
                output_chars += len(chunk)
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        temp_path.replace(output_path)
    except Exception:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
        raise
    elapsed_ms = (perf_counter() - start) * 1000
    record_render_metrics(parsed, output_path, output_chars, elapsed_ms)
    write_metrics_debug(parsed)
    return {"html": str(output_path)}


def to_html5(parsed: ParsedDocument, density: Density | str = Density.SEMANTIC) -> str:
    """Return the complete markup string at the given density."""
    return "".join(iter_html5(parsed, density))


def iter_html5(parsed: ParsedDocument, density: Density | str = Density.SEMANTIC) -> Iterator[str]:
    """Yield markup chunks for streaming output."""
    resolved_density = Density.parse(density)
    if resolved_density is Density.PLAIN:
        yield from iter_l0(parsed)
    elif resolved_density is Density.STRUCTURAL:
        yield from iter_l1(parsed)
    else:
        yield from iter_l2(parsed)


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
    start_block = page_index.get(start_page, (0,))[0] if start_page in page_index else 0
    end_block = page_index.get(end_page, (len(parsed.blocks) - 1,))
    end_idx = end_block[1] if len(end_block) > 1 else end_block[0]

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
