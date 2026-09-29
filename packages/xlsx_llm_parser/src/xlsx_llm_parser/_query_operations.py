"""query operations."""

from __future__ import annotations

from ._query_types import AggregateSpec, OrderSpec, WhereCondition


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
