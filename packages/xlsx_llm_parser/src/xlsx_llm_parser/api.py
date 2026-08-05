"""Public API — accepts source files directly, returns rendered results."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .parser import parse_xlsx
from .renderers.structural import (
    _find_sheet,
    _parse_range,
    _render_grid,
    _render_sheet,
)


def render_workbook(source: str | Path | bytes, *, density: str = "structural") -> str:
    """Parse *source* and render the entire workbook at the given density."""
    wb = parse_xlsx(source)
    parts = [f"density={density}\n"]
    for sheet in wb["sheets"]:
        parts.extend(_render_sheet(sheet, density, wb))
    return "".join(parts)


def iter_workbook(source: str | Path | bytes, *, density: str = "structural") -> Iterator[str]:
    """Stream workbook rendering chunks from *source*."""
    wb = parse_xlsx(source)
    yield f"density={density}\n"
    for sheet in wb["sheets"]:
        yield from _render_sheet(sheet, density, wb)


def render_range(
    source: str | Path | bytes,
    sheet: str,
    range_spec: str,
    *,
    density: str = "structural",
) -> str:
    """Render cells within an A1-style range from *source*."""
    wb = parse_xlsx(source)
    sheet_info = _find_sheet(wb, sheet)
    start_col, start_row, end_col, end_row = _parse_range(range_spec)

    rows = sheet_info.get("rows", [])
    filtered = []
    for row_cells in rows:
        kept = [
            c
            for c in row_cells
            if start_col <= c["col"] <= end_col and start_row <= c["row"] <= end_row
        ]
        if kept:
            filtered.append(kept)

    return _render_grid(filtered, density, wb)
