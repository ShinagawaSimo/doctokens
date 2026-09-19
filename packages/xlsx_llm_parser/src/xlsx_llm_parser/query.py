"""Query helpers for parsed XLSX table and range data."""

from __future__ import annotations

from html import escape as escape_text
from typing import TypedDict

from ._utils import col_letter
from .models import Cell, ParsedWorkbook, SheetInfo
from .rendering.structural import _find_sheet, _parse_range


class WhereCondition(TypedDict, total=False):
    column: str
    op: str
    value: object


AggregateSpec = TypedDict(
    "AggregateSpec",
    {"op": str, "column": str, "as": str},
    total=False,
)


class OrderSpec(TypedDict, total=False):
    column: str
    direction: str


class QueryColumn(TypedDict):
    key: str
    label: str
    col: int


_WHERE_OPS = {"eq", "contains", "gt", "lt"}
_AGGREGATE_OPS = {"sum", "count", "avg", "min", "max"}
_ORDER_DIRECTIONS = {"asc", "desc"}


def query_data(
    parsed_workbook: ParsedWorkbook,
    *,
    table_id: str | None = None,
    sheet: str | None = None,
    range_spec: str | None = None,
    header_row: int | None = None,
    select: list[str] | None = None,
    where: list[WhereCondition] | None = None,
    group_by: list[str] | None = None,
    aggregates: list[AggregateSpec] | None = None,
    order_by: list[OrderSpec] | None = None,
    limit: int | None = None,
) -> str:
    """Query a declared table or explicit range and return tabular output."""
    query_sheet, query_columns, range_bounds, header_row_to_skip = _resolve_query_source(
        parsed_workbook,
        table_id=table_id,
        sheet=sheet,
        range_spec=range_spec,
        header_row=header_row,
    )
    start_col, start_row, end_col, end_row = range_bounds
    query_rows = _rows_in_range(query_sheet, start_col, start_row, end_col, end_row)
    query_columns = _columns_from_optional_header(query_rows, query_columns, header_row, start_col, end_col)
    result_rows = _materialize_rows(query_rows, query_columns, start_col, end_col, header_row_to_skip)

    if where:
        result_rows = _apply_where(result_rows, _resolve_where_conditions(where, query_columns))

    if group_by and aggregates:
        resolved_group_by = [_resolve_column_key(group_name, query_columns) for group_name in group_by]
        resolved_aggregates = _resolve_aggregates(aggregates, query_columns)
        result_rows = _apply_aggregation(result_rows, resolved_group_by, resolved_aggregates)
        query_columns = _aggregation_columns(resolved_group_by, resolved_aggregates, query_columns)

    if select and result_rows:
        query_columns = _select_columns(select, query_columns)
        selected_column_keys = [column["key"] for column in query_columns]
        result_rows = [
            {column_key: row.get(column_key, "") for column_key in selected_column_keys if column_key in row}
            for row in result_rows
        ]

    if order_by:
        result_rows = _apply_order_by(result_rows, _resolve_order_specs(order_by, query_columns))

    if limit and limit > 0:
        result_rows = result_rows[:limit]

    return _render_query_result(result_rows, query_columns)


def _resolve_query_source(
    parsed_workbook: ParsedWorkbook,
    *,
    table_id: str | None,
    sheet: str | None,
    range_spec: str | None,
    header_row: int | None,
) -> tuple[SheetInfo, list[QueryColumn], tuple[int, int, int, int], int | None]:
    if table_id is not None:
        for sheet_info in parsed_workbook["sheets"]:
            for table in sheet_info.get("tables", []):
                if table["id"] == table_id:
                    bounds = _parse_range(table["ref"])
                    start_col, _start_row, end_col, _end_row = bounds
                    table_columns = [str(item) for item in table.get("columns", [])]
                    columns = _columns_from_labels(table_columns, start_col, end_col)
                    return sheet_info, columns, bounds, bounds[1]
        raise ValueError(f"Table {table_id!r} not found")

    if sheet is not None and range_spec is not None and header_row is not None:
        sheet_info = _find_sheet(parsed_workbook, sheet)
        return sheet_info, [], _parse_range(range_spec), header_row

    raise ValueError("Provide table_id or (sheet + range_spec + header_row)")


def _columns_from_optional_header(
    source_rows: list[list[Cell]],
    columns: list[QueryColumn],
    header_row: int | None,
    start_col: int,
    end_col: int,
) -> list[QueryColumn]:
    if columns or header_row is None:
        return columns
    for row_cells in source_rows:
        if row_cells[0]["row"] == header_row:
            return _columns_from_header(row_cells, start_col, end_col)
    return columns


def _materialize_rows(
    source_rows: list[list[Cell]],
    columns: list[QueryColumn],
    start_col: int,
    end_col: int,
    skip_rows_through: int | None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row_cells in source_rows:
        row_number = row_cells[0]["row"]
        if skip_rows_through is not None and row_number <= skip_rows_through:
            continue
        row = _row_to_dict(row_cells, columns, start_col, end_col)
        if row:
            row["__row"] = row_number
            rows.append(row)
    return rows


def _rows_in_range(
    sheet_obj: SheetInfo,
    start_col: int,
    start_row: int,
    end_col: int,
    end_row: int,
) -> list[list[Cell]]:
    rows: list[list[Cell]] = []
    for row_cells in sheet_obj.get("rows", []):
        if not row_cells:
            continue
        row_num = row_cells[0]["row"]
        if row_num < start_row:
            continue
        if row_num > end_row:
            break
        rows.append(row_cells)
    return rows


def _columns_from_header(row_cells: list[Cell], start_col: int, end_col: int) -> list[QueryColumn]:
    labels = ["" for _col in range(start_col, end_col + 1)]
    for cell in row_cells:
        if start_col <= cell["col"] <= end_col:
            text = str(cell.get("text", "")).strip()
            labels[cell["col"] - start_col] = text
    return _columns_from_labels(labels, start_col, end_col)


def _columns_from_labels(labels: list[str], start_col: int, end_col: int) -> list[QueryColumn]:
    columns: list[QueryColumn] = []
    seen: dict[str, int] = {}
    for col in range(start_col, end_col + 1):
        label = labels[col - start_col].strip() if col - start_col < len(labels) else ""
        key_base = label or f"__col{col}"
        seen[key_base] = seen.get(key_base, 0) + 1
        key = key_base if seen[key_base] == 1 else f"{key_base}_{seen[key_base]}"
        columns.append({"key": key, "label": label, "col": col})
    return columns


def _row_to_dict(
    row_cells: list[Cell],
    columns: list[QueryColumn],
    start_col: int,
    end_col: int,
) -> dict[str, object]:
    row_dict: dict[str, object] = {}
    for cell in row_cells:
        if start_col <= cell["col"] <= end_col:
            col_idx = cell["col"] - start_col
            col_name = columns[col_idx]["key"] if col_idx < len(columns) else f"__col{cell['col']}"
            row_dict[col_name] = _coerce_cell_value(cell.get("text", ""))
    return row_dict


def _resolve_where_conditions(
    conditions: list[WhereCondition],
    columns: list[QueryColumn],
) -> list[WhereCondition]:
    resolved: list[WhereCondition] = []
    for condition in conditions:
        item: WhereCondition = {}
        if "column" not in condition:
            raise ValueError("where condition requires a 'column'")
        item["column"] = _resolve_column_key(condition["column"], columns)
        if "op" in condition:
            op = str(condition["op"])
            if op not in _WHERE_OPS:
                raise ValueError(f"Unsupported where operator {op!r}; expected one of {sorted(_WHERE_OPS)}")
            item["op"] = op
        if "value" in condition:
            item["value"] = condition["value"]
        resolved.append(item)
    return resolved


def _resolve_aggregates(
    aggregates: list[AggregateSpec],
    columns: list[QueryColumn],
) -> list[AggregateSpec]:
    resolved: list[AggregateSpec] = []
    for aggregate in aggregates:
        item: AggregateSpec = {}
        if "op" in aggregate:
            op = str(aggregate["op"])
            if op not in _AGGREGATE_OPS:
                raise ValueError(f"Unsupported aggregate operator {op!r}; expected one of {sorted(_AGGREGATE_OPS)}")
            item["op"] = op
        if "column" in aggregate:
            item["column"] = _resolve_column_key(aggregate["column"], columns)
        if "as" in aggregate:
            item["as"] = aggregate["as"]
        resolved.append(item)
    return resolved


def _resolve_order_specs(
    order_specs: list[OrderSpec],
    columns: list[QueryColumn],
) -> list[OrderSpec]:
    resolved: list[OrderSpec] = []
    for order_spec in order_specs:
        item: OrderSpec = {}
        if "column" in order_spec:
            item["column"] = _resolve_column_key(order_spec["column"], columns)
        if "direction" in order_spec:
            direction = str(order_spec["direction"])
            if direction not in _ORDER_DIRECTIONS:
                raise ValueError(f"Unsupported sort direction {direction!r}; expected one of {sorted(_ORDER_DIRECTIONS)}")
            item["direction"] = direction
        resolved.append(item)
    return resolved


def _resolve_column_key(name: str, columns: list[QueryColumn]) -> str:
    value = str(name)
    for column in columns:
        if value in {column["key"], column["label"]}:
            return column["key"]
    for column in columns:
        if value in {col_letter(column["col"]), f"Col{column['col']}"}:
            return column["key"]
    available = ", ".join(repr(column["key"]) for column in columns) or "none"
    raise ValueError(f"Column {value!r} not found; available columns: {available}")


def _select_columns(select: list[str], columns: list[QueryColumn]) -> list[QueryColumn]:
    selected: list[QueryColumn] = []
    for item in select:
        key = _resolve_column_key(item, columns)
        column = _find_column(key, columns)
        selected.append(column if column is not None else {"key": key, "label": key, "col": 0})
    return selected


def _find_column(key: str, columns: list[QueryColumn]) -> QueryColumn | None:
    for column in columns:
        if column["key"] == key:
            return column
    return None


def _aggregation_columns(
    group_by: list[str],
    aggregates: list[AggregateSpec],
    source_columns: list[QueryColumn],
) -> list[QueryColumn]:
    columns: list[QueryColumn] = []
    for key in group_by:
        source = _find_column(key, source_columns)
        columns.append(source if source is not None else {"key": key, "label": key, "col": 0})
    for aggregate in aggregates:
        op = aggregate.get("op", "sum")
        col = str(aggregate.get("column", ""))
        output_name = _aggregate_name(aggregate, op, col)
        columns.append({"key": output_name, "label": output_name, "col": 0})
    return columns


def _coerce_cell_value(raw: object) -> object:
    text = str(raw)
    try:
        return float(text) if "." in text else int(text)
    except (ValueError, TypeError):
        return text


def _apply_where(
    rows: list[dict[str, object]],
    conditions: list[WhereCondition],
) -> list[dict[str, object]]:
    return [row for row in rows if all(_matches_condition(row, condition) for condition in conditions)]


def _matches_condition(row: dict[str, object], condition: WhereCondition) -> bool:
    col = str(condition.get("column", ""))
    op = condition.get("op", "eq")
    expected = condition.get("value")
    actual = row.get(col)

    if op == "eq":
        return str(actual) == str(expected)
    if op == "contains":
        return str(expected).lower() in str(actual).lower()
    if op in ("gt", "lt"):
        if not isinstance(actual, (int, float)):
            return False
        try:
            expected_num = float(str(expected))
        except (ValueError, TypeError):
            return False
        return actual > expected_num if op == "gt" else actual < expected_num
    return False


def _apply_aggregation(
    rows: list[dict[str, object]],
    group_by: list[str],
    aggregates: list[AggregateSpec],
) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], dict[str, object]] = {}
    for row in rows:
        key = tuple(row.get(group, "") for group in group_by)
        groups.setdefault(key, {group: row.get(group, "") for group in group_by})
        _update_group(groups[key], row, aggregates)

    for row in groups.values():
        _finalize_averages(row, aggregates)
    return list(groups.values())


def _update_group(
    group: dict[str, object],
    row: dict[str, object],
    aggregates: list[AggregateSpec],
) -> None:
    for agg in aggregates:
        op = agg.get("op", "sum")
        col = str(agg.get("column", ""))
        output_name = _aggregate_name(agg, op, col)
        value = row.get(col)

        if op == "count":
            group[output_name] = _numeric_value(group.get(output_name), 0) + 1
            continue
        if not isinstance(value, (int, float)):
            continue
        if op == "sum":
            group[output_name] = _numeric_value(group.get(output_name), 0) + value
        elif op == "avg":
            group[output_name] = _average_accumulator(group.get(output_name), value)
        elif op == "min":
            group[output_name] = min(_numeric_value(group.get(output_name), value), value)
        elif op == "max":
            group[output_name] = max(_numeric_value(group.get(output_name), value), value)


def _average_accumulator(existing: object, value: float | int) -> tuple[float | int, int]:
    if not isinstance(existing, tuple) or len(existing) != 2:
        return (value, 1)
    total, count = existing
    if isinstance(total, (int, float)) and isinstance(count, int):
        return (total + value, count + 1)
    return (value, 1)


def _finalize_averages(row: dict[str, object], aggregates: list[AggregateSpec]) -> None:
    for agg in aggregates:
        if agg.get("op") != "avg":
            continue
        col = str(agg.get("column", ""))
        output_name = _aggregate_name(agg, "avg", col)
        existing = row.get(output_name)
        if not isinstance(existing, tuple) or len(existing) != 2:
            row[output_name] = 0
            continue
        total, count = existing
        if isinstance(total, (int, float)) and isinstance(count, int) and count:
            row[output_name] = round(total / count, 4)
        else:
            row[output_name] = 0


def _aggregate_name(agg: AggregateSpec, op: str, column: str) -> str:
    alias = agg.get("as")
    return alias if alias else f"{op}_{column}"


def _numeric_value(value: object, default: float | int) -> float | int:
    return value if isinstance(value, (int, float)) else default


def _apply_order_by(
    rows: list[dict[str, object]],
    order_specs: list[OrderSpec],
) -> list[dict[str, object]]:
    ordered_rows = list(rows)
    for order_spec in reversed(order_specs):
        col = str(order_spec.get("column", ""))
        desc = order_spec.get("direction") == "desc"
        ordered_rows.sort(key=lambda row: _order_key(row, col), reverse=desc)
    return ordered_rows


def _order_key(row: dict[str, object], column: str) -> tuple[int, object]:
    """Type-aware sort key: numbers sort numerically before strings."""
    value = row.get(column, "")
    if isinstance(value, (int, float)):
        return (0, value)
    return (1, str(value))


def _render_query_result(rows: list[dict[str, object]], columns: list[QueryColumn] | None = None) -> str:
    if not rows:
        return "<table>\n"
    all_cols: list[QueryColumn]
    if columns is None:
        all_cols = [{"key": col, "label": col, "col": 0} for col in rows[0] if col != "__row"]
    else:
        all_cols = [col for col in columns if any(col["key"] in row for row in rows)]
    parts = ["<table>\n<tr>"]
    parts.extend(f"<th>{escape_text(column['label'])}" for column in all_cols)
    for row in rows:
        parts.append("<tr>")
        parts.extend(f"<td>{escape_text(str(row.get(column['key'], '')))}" for column in all_cols)
    return "".join(parts) + "\n"
