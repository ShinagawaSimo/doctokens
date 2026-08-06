"""Public API — accepts source files directly, returns rendered results."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape
from pathlib import Path

from .parser import _parse_workbook
from .renderers.structural import (
    _find_sheet,
    _parse_range,
    _render_grid,
    _render_sheet,
)


def parse_xlsx(source: str | Path | bytes, *, density: str = "structural",
               start_row: int = 1) -> str:
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


def iter_workbook(source: str | Path | bytes, *, density: str = "structural",
                  start_row: int = 1) -> Iterator[str]:
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
                        f'<match field=definedName>'
                        f"{escape(dn['name'])} = {escape(dn['ref'])}"
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

    # Resolve data source
    rows: list[list] = []
    columns: list[str] = []
    if table_id is not None:
        for s in wb["sheets"]:
            for t in s.get("tables", []):
                if t["id"] == table_id:
                    sheet_obj = s
                    columns = t.get("columns", [])
                    start_col, start_row, end_col, end_row = _parse_range(t["ref"])
                    break
            else:
                continue
            break
        else:
            raise ValueError(f"Table {table_id!r} not found")
    elif sheet and range_spec and header_row:
        sheet_obj = _find_sheet(wb, sheet)
        start_col, start_row, end_col, end_row = _parse_range(range_spec)
        columns = []
    else:
        raise ValueError("Provide table_id or (sheet + range_spec + header_row)")

    # Collect rows (header + data)
    typed_rows: list[dict[str, object]] = []
    for row_cells in sheet_obj.get("rows", []):
        if not row_cells:
            continue
        row_num = row_cells[0]["row"]
        if row_num < start_row:
            continue
        if row_num > end_row:
            break
        row_dict: dict[str, object] = {}
        for c in row_cells:
            if start_col <= c["col"] <= end_col:
                col_idx = c["col"] - start_col
                col_name = columns[col_idx] if col_idx < len(columns) else f"Col{c['col']}"
                raw = c.get("text", "")
                try:
                    if "." in str(raw):
                        row_dict[col_name] = float(str(raw))
                    else:
                        row_dict[col_name] = int(str(raw))
                except (ValueError, TypeError):
                    row_dict[col_name] = str(raw)
        if row_dict:
            row_dict["__row"] = row_num
            typed_rows.append(row_dict)

    # Header row detection — extract column names from data
    if not columns and header_row:
        for r in typed_rows:
            if r.get("__row") == header_row:
                columns = [str(v) for k, v in r.items() if k != "__row"]
                break

    # Filtering
    if where:
        filtered: list[dict[str, object]] = []
        for row in typed_rows:
            match = True
            for cond in where:
                col = str(cond.get("column", ""))
                op = cond.get("op", "eq")
                val = cond.get("value")
                cell_val = row.get(col)
                if op == "eq" and str(cell_val) != str(val):
                    match = False
                elif op == "contains" and str(val).lower() not in str(cell_val).lower():
                    match = False
                elif op in ("gt", "lt"):
                    if not isinstance(cell_val, (int, float)):
                        match = False
                    else:
                        try:
                            num_val = float(str(val))
                        except (ValueError, TypeError):
                            match = False
                        else:
                            if op == "gt" and cell_val <= num_val:
                                match = False
                            elif op == "lt" and cell_val >= num_val:
                                match = False
            if match:
                filtered.append(row)
        typed_rows = filtered

    # Column projection (select)
    if select and typed_rows:
        keep_cols = [str(s) for s in select]

    # Aggregation
    if group_by and aggregates:
        groups: dict[tuple, dict[str, object]] = {}
        for row in typed_rows:
            key = tuple(row.get(g, "") for g in group_by)
            if key not in groups:
                groups[key] = {g: row.get(g, "") for g in group_by}
            for agg in aggregates:
                op = agg.get("op", "sum")
                col = str(agg.get("column", ""))
                as_name = agg.get("as", f"{op}_{col}")
                val = row.get(col)
                if op == "count":
                    groups[key][as_name] = groups[key].get(as_name, 0) + 1
                    continue
                if not isinstance(val, (int, float)):
                    continue
                if op == "sum":
                    groups[key][as_name] = groups[key].get(as_name, 0) + val
                elif op == "avg":
                    cur = groups[key].get(as_name, (0, 0))
                    groups[key][as_name] = (cur[0] + val, cur[1] + 1)
                elif op == "min":
                    groups[key][as_name] = min(groups[key].get(as_name, val), val)
                elif op == "max":
                    groups[key][as_name] = max(groups[key].get(as_name, val), val)
        # Finalize averages
        for key in groups:
            for agg in aggregates:
                if agg.get("op") == "avg":
                    as_name = agg.get("as", f"avg_{agg['column']}")
                    cur = groups[key].get(as_name)
                    if isinstance(cur, tuple):
                        groups[key][as_name] = round(cur[0] / cur[1], 4) if cur[1] else 0
                    elif cur is None:
                        groups[key][as_name] = 0
        typed_rows = list(groups.values())

    # Column projection applied after aggregation too
    if select and typed_rows:
        keep_cols = [str(s) for s in select]
        typed_rows = [{c: r.get(c, "") for c in keep_cols if c in r} for r in typed_rows]

    # Sorting
    if order_by:
        for ob in reversed(order_by):
            col = str(ob.get("column", ""))
            desc = ob.get("direction") == "desc"
            typed_rows.sort(key=lambda r, c=col: str(r.get(c, "")), reverse=desc)

    # Limit
    if limit and limit > 0:
        typed_rows = typed_rows[:limit]

    # Render
    if not typed_rows:
        return "<table>\n"
    all_cols = list(typed_rows[0].keys())
    all_cols = [c for c in all_cols if c != "__row"]
    parts = ["<table>\n<tr>"]
    for col in all_cols:
        parts.append(f"<th>{escape(str(col))}")
    for row in typed_rows:
        parts.append("<tr>")
        for col in all_cols:
            parts.append(f"<td>{escape(str(row.get(col, '')))}")
    return "".join(parts) + "\n"


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
                    return {"type": "chart", "id": resource_id, "ref": ch["ref"]}
    elif resource_type == "pivot_table":
        for s in wb["sheets"]:
            for pv in s.get("pivot_tables", []):
                if pv["id"] == resource_id:
                    return {"type": "pivot_table", "id": resource_id, "name": pv.get("name", "")}
    return None
