"""Public API — accepts source files directly, returns rendered results."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape
from pathlib import Path

from .parser import _parse_workbook
from .query import query_data as _query_data
from .renderers.structural import (
    _find_sheet,
    _parse_range,
    _render_grid,
    _render_sheet,
)


def parse_xlsx(
    source: str | Path | bytes, *, density: str = "structural", start_row: int = 1
) -> str:
    """Parse *source* and render the entire workbook at the given density.

    *start_row* (1-based) begins rendering from the specified row for the
    first data sheet, enabling paginated window reads of large grids.
    """
    wb = _parse_workbook(source)
    parts = [f"density={density}\n"]
    for sheet in wb["sheets"]:
        parts.extend(_render_sheet(sheet, density, wb, start_row=start_row))
        # start_row only applies to first non-chartsheet; subsequent sheets
        # always render from row 1.
        if sheet.get("kind") != "chartsheet" and start_row != 1:
            start_row = 1
    return "".join(parts)


def iter_workbook(
    source: str | Path | bytes, *, density: str = "structural", start_row: int = 1
) -> Iterator[str]:
    """Stream workbook rendering chunks from *source*."""
    wb = _parse_workbook(source)
    yield f"density={density}\n"
    for sheet in wb["sheets"]:
        yield from _render_sheet(sheet, density, wb, start_row=start_row)
        if sheet.get("kind") != "chartsheet" and start_row != 1:
            start_row = 1


def render_range(
    source: str | Path | bytes,
    sheet: str,
    range_spec: str,
    *,
    density: str = "structural",
) -> str:
    """Render cells within an A1-style range from *source*."""
    wb = _parse_workbook(source)
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


def find_cells(
    source: str | Path | bytes,
    query: str,
    *,
    sheets: list[str] | None = None,
    kind: str | None = None,
    limit: int = 50,
) -> str:
    """Search values, formulas, comments, and defined names across sheets.

    *kind* narrows to one of ``value``, ``formula``, ``comment``, ``definedName``.
    """
    import re as _re

    if not query:
        return "<matches>\n"
    wb = _parse_workbook(source)
    pattern = _re.compile(_re.escape(query))  # exact match by default
    matches: list[str] = []
    sheets_to_search = sheets or [s["name"] for s in wb["sheets"]]

    for sheet_name in sheets_to_search:
        if len(matches) >= limit:
            break
        sheet = _find_sheet(wb, sheet_name)
        for row_cells in sheet.get("rows", []):
            for cell in row_cells:
                if len(matches) >= limit:
                    break
                if kind is None or kind == "value":
                    if pattern.search(cell.get("text", "")):
                        matches.append(
                            f'<match cell="{escape(sheet_name, quote=True)}!{cell["ref"]}" field=value>'
                            f"{escape(cell['text'])}"
                        )
                        continue
                if kind is None or kind == "formula":
                    if pattern.search(cell.get("formula", "")):
                        matches.append(
                            f'<match cell="{escape(sheet_name, quote=True)}!{cell["ref"]}" field=formula>'
                            f"{escape(cell.get('formula', ''))}"
                        )
                        continue
                if kind is None or kind == "comment":
                    if pattern.search(cell.get("comment", "")):
                        matches.append(
                            f'<match cell="{escape(sheet_name, quote=True)}!{cell["ref"]}" field=comment>'
                            f"{escape(cell.get('comment', ''))}"
                        )
            if len(matches) >= limit:
                break

        # Defined names
        if (kind is None or kind == "definedName") and len(matches) < limit:
            for dn in wb.get("metadata", {}).get("defined_names", []):
                if len(matches) >= limit:
                    break
                scope = dn.get("scopeSheet")
                if scope and scope != sheet_name:
                    continue
                if pattern.search(dn["name"]) or pattern.search(dn.get("ref", "")):
                    matches.append(
                        f"<match field=definedName>{escape(dn['name'])} = {escape(dn['ref'])}"
                    )

    parts = ["<matches>\n"]
    parts.append("\n".join(matches[:limit]))
    return "".join(parts) + "\n"


def query_data(
    source: str | Path | bytes,
    *,
    table_id: str | None = None,
    sheet: str | None = None,
    range_spec: str | None = None,
    header_row: int | None = None,
    select: list[str] | None = None,
    where: list[dict] | None = None,
    group_by: list[str] | None = None,
    aggregates: list[dict] | None = None,
    order_by: list[dict] | None = None,
    limit: int | None = None,
) -> str:
    """Query a declared Table or explicit range with projection, filtering,
    grouping, and aggregation.  Returns lightweight tabular HTML.
    """
    wb = _parse_workbook(source)
    return _query_data(
        wb,
        table_id=table_id,
        sheet=sheet,
        range_spec=range_spec,
        header_row=header_row,
        select=select,
        where=where,
        group_by=group_by,
        aggregates=aggregates,
        order_by=order_by,
        limit=limit,
    )


def get_resource(
    source: str | Path | bytes,
    resource_type: str,
    resource_id: str,
) -> dict | None:
    """Return a lightweight resource by type and ID.

    *resource_type*: ``image``, ``chart``, ``pivot_table``, ``embedded_object``.
    """
    wb = _parse_workbook(source)

    if resource_type == "image":
        for s in wb["sheets"]:
            for img in s.get("images", []):
                if img["id"] == resource_id:
                    return {"type": "image", "id": resource_id, "ref": img["ref"]}
    elif resource_type == "chart":
        for s in wb["sheets"]:
            for ch in s.get("charts", []):
                if ch["id"] == resource_id:
                    result: dict = {
                        "type": "chart",
                        "id": ch["id"],
                        "ref": ch["ref"],
                        "chartType": ch.get("type", ""),
                        "seriesCount": ch.get("series_count", 0),
                    }
                    if ch.get("title"):
                        result["title"] = ch["title"]
                    if ch.get("part"):
                        result["part"] = ch["part"]
                    if ch.get("series"):
                        result["series"] = ch["series"]
                    return result
    elif resource_type == "pivot_table":
        for s in wb["sheets"]:
            for pv in s.get("pivot_tables", []):
                if pv["id"] == resource_id:
                    return {"type": "pivot_table", "id": resource_id, "name": pv.get("name", "")}
    return None
