"""Row-at-a-time query projection and aggregation, preserving query semantics."""

from __future__ import annotations

from ooxml_llm_core.execution import checkpoint

from ._query_columns import (
    _aggregation_columns,
    _resolve_aggregates,
    _resolve_column_key,
    _resolve_order_specs,
    _resolve_where_conditions,
    _select_columns,
)
from ._query_operations import _apply_order_by, _coerce_cell_value, _finalize_averages, _matches_condition, _update_group
from ._query_types import AggregateSpec, OrderSpec, QueryColumn, WhereCondition
from .models import Cell


class QueryPipeline:
    def __init__(
        self,
        columns: list[QueryColumn],
        *,
        where: list[WhereCondition] | None = None,
        group_by: list[str] | None = None,
        aggregates: list[AggregateSpec] | None = None,
        select: list[str] | None = None,
        order_by: list[OrderSpec] | None = None,
        limit: int | None = None,
    ) -> None:
        self.source_columns = columns
        self.columns = columns
        self.where = _resolve_where_conditions(where, columns) if where else []
        self.group_by = [_resolve_column_key(name, columns) for name in group_by] if group_by and aggregates else []
        self.aggregates = _resolve_aggregates(aggregates, columns) if group_by and aggregates else []
        self.grouping = bool(group_by and aggregates)
        self.select = select
        self.order_by = order_by
        self.limit = limit if limit is not None and limit > 0 else None
        self.rows: list[dict[str, object]] = []
        self.groups: dict[tuple[object, ...], dict[str, object]] = {}
        self.complete = False
        self._selected: list[QueryColumn] | None = None
        self._source_keys = {column["col"]: column["key"] for column in columns}
        if self.grouping:
            needed = set(self.group_by) | {item["column"] for item in self.aggregates if "column" in item}
            self.columns = _aggregation_columns(self.group_by, self.aggregates, columns)
        elif select:
            try:
                needed = {column["key"] for column in _select_columns(select, columns)}
            except ValueError:
                # Selection errors historically occur only if a row survives
                # the filter. Keep that validation timing for empty results.
                needed = set(self._source_keys.values())
        else:
            needed = set(self._source_keys.values())
        needed.update(item["column"] for item in self.where)
        self.required_columns = frozenset(column["col"] for column in columns if column["key"] in needed)

    def consume(self, row_number: int, cells: list[Cell]) -> bool:
        checkpoint("querying saved rows")
        if self.complete:
            return False
        row = {
            self._source_keys[cell["col"]]: _coerce_cell_value(cell.get("text", ""))
            for cell in cells
            if cell["col"] in self.required_columns
        }
        row["__row"] = row_number
        if not all(_matches_condition(row, condition) for condition in self.where):
            return True
        if self.grouping:
            key = tuple(row.get(name, "") for name in self.group_by)
            group = self.groups.setdefault(key, {name: row.get(name, "") for name in self.group_by})
            _update_group(group, row, self.aggregates)
        else:
            if self.select:
                if self._selected is None:
                    self._selected = _select_columns(self.select, self.source_columns)
                    self.columns = self._selected
                row = {column["key"]: row[column["key"]] for column in self._selected if column["key"] in row}
            self.rows.append(row)
            if not self.order_by and self.limit is not None and len(self.rows) >= self.limit:
                self.complete = True
        return not self.complete

    def finish(self) -> tuple[list[dict[str, object]], list[QueryColumn]]:
        checkpoint("finalizing query")
        rows = list(self.groups.values()) if self.grouping else self.rows
        if self.grouping:
            for row in rows:
                _finalize_averages(row, self.aggregates)
            if self.select and rows:
                self.columns = _select_columns(self.select, self.columns)
                rows = [{column["key"]: row[column["key"]] for column in self.columns if column["key"] in row} for row in rows]
        if self.order_by:
            rows = _apply_order_by(rows, _resolve_order_specs(self.order_by, self.columns))
        if self.limit is not None:
            rows = rows[: self.limit]
        checkpoint("query ready")
        return rows, self.columns
