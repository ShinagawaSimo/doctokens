"""Query engine — projection, filtering, grouping, and aggregation over table/range data.

Accepts a pre-parsed workbook and query parameters; returns rendered tabular HTML.
"""

from __future__ import annotations

from html import escape

from .renderers.structural import _find_sheet, _parse_range


def query_data(
    wb,
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
    # ── Resolve data source ──
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

    # ── Collect rows (header + data) ──
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

    # ── Header row detection ──
    if not columns and header_row:
        for r in typed_rows:
            if r.get("__row") == header_row:
                columns = [str(v) for k, v in r.items() if k != "__row"]
                break

    # ── Filtering ──
    if where:
        typed_rows = _apply_where(typed_rows, where)

    # ── Aggregation ──
    if group_by and aggregates:
        typed_rows = _apply_aggregation(typed_rows, group_by, aggregates)

    # ── Column projection ──
    if select and typed_rows:
        keep_cols = [str(s) for s in select]
        typed_rows = [{c: r.get(c, "") for c in keep_cols if c in r} for r in typed_rows]

    # ── Sorting ──
    if order_by:
        typed_rows = _apply_order_by(typed_rows, order_by)

    # ── Limit ──
    if limit and limit > 0:
        typed_rows = typed_rows[:limit]

    # ── Render ──
    return _render_query_result(typed_rows)


def _apply_where(rows: list[dict[str, object]], conditions: list[dict]) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for row in rows:
        match = True
        for cond in conditions:
            col = str(cond.get("column", ""))
            op = cond.get("op", "eq")
            val = cond.get("value")
            cell_val = row.get(col)
            if (op == "eq" and str(cell_val) != str(val)) or (
                op == "contains" and str(val).lower() not in str(cell_val).lower()
            ):
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
                        if (op == "gt" and cell_val <= num_val) or (
                            op == "lt" and cell_val >= num_val
                        ):
                            match = False
        if match:
            filtered.append(row)
    return filtered


def _apply_aggregation(
    rows: list[dict[str, object]],
    group_by: list[str],
    aggregates: list[dict],
) -> list[dict[str, object]]:
    groups: dict[tuple, dict[str, object]] = {}
    for row in rows:
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
    return list(groups.values())


def _apply_order_by(
    rows: list[dict[str, object]], order_specs: list[dict]
) -> list[dict[str, object]]:
    result = list(rows)
    for ob in reversed(order_specs):
        col = str(ob.get("column", ""))
        desc = ob.get("direction") == "desc"
        result.sort(key=lambda r, c=col: str(r.get(c, "")), reverse=desc)
    return result


def _render_query_result(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "<table>\n"
    all_cols = list(rows[0].keys())
    all_cols = [c for c in all_cols if c != "__row"]
    parts = ["<table>\n<tr>"]
    for col in all_cols:
        parts.append(f"<th>{escape(str(col))}")
    for row in rows:
        parts.append("<tr>")
        for col in all_cols:
            parts.append(f"<td>{escape(str(row.get(col, '')))}")
    return "".join(parts) + "\n"
