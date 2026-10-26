"""Column identity and validation shared by parsed and projected XLSX queries."""

from __future__ import annotations

from ..model.coordinates import col_letter
from ..model.workbook import Cell
from .operations import _aggregate_name
from .types import AggregateSpec, OrderSpec, QueryColumn, WhereCondition

_WHERE_OPS = {"eq", "contains", "gt", "lt"}
_AGGREGATE_OPS = {"sum", "count", "avg", "min", "max"}
_ORDER_DIRECTIONS = {"asc", "desc"}


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
