"""Minimal source query execution without constructing a workbook read session."""

from __future__ import annotations

from dataclasses import replace

from doctokens_core.contracts.models import ParseResult, Source

from ..model.workbook import Cell, ParseOptions
from ..parsing.plan import XlsxParsePlan
from ..parsing.source import OperationSource
from .columns import _columns_from_header
from .engine import _render_query_result, _resolve_query_source, query_data
from .pipeline import QueryPipeline
from .types import AggregateSpec, OrderSpec, WhereCondition


def query_xlsx(
    source: Source,
    *,
    options: ParseOptions | None = None,
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
) -> ParseResult:
    with OperationSource(source, options) as opened:
        if table_id is not None:
            opened.tables()
        target, columns, bounds, skip = _resolve_query_source(
            opened.workbook(), table_id=table_id, sheet=sheet, range_spec=range_spec, header_row=header_row
        )
        preflight = opened.preflight(target, bounds, header_row if table_id is None else None)
        left, top, right, bottom = bounds
        if not columns and header_row is not None:
            header = next((row for row in preflight.rows if row[0]["row"] == header_row and top <= header_row <= bottom), None)
            if header is not None:
                columns = _columns_from_header(header, left, right)
        pipeline = QueryPipeline(
            columns, select=select, where=where, group_by=group_by, aggregates=aggregates, order_by=order_by, limit=limit
        )
        plan = XlsxParsePlan.values(target["name"], window=bounds, columns=pipeline.required_columns)
        if not preflight.ordered_rows:
            target["rows"] = opened.scan(
                target,
                replace(
                    plan,
                    columns=None,
                    annotation_cells=True,
                    features=XlsxParsePlan.values(target["name"], annotations=True).features,
                ),
            ).rows
            return opened.result(
                query_data(
                    opened.workbook(),
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
                ),
                "query",
            )
        annotations = {
            row[0]["row"]: [cell for cell in row if left <= cell["col"] <= right]
            for row in preflight.rows
            if top <= row[0]["row"] <= bottom and (skip is None or row[0]["row"] > skip)
        }
        pending = iter(sorted(number for number, cells in annotations.items() if cells))
        next_row = next(pending, None)

        def consume(number: int, cells: list[Cell]) -> bool:
            nonlocal next_row
            while next_row is not None and next_row < number and not pipeline.complete:
                pipeline.consume(next_row, annotations[next_row])
                next_row = next(pending, None)
            if next_row == number:
                present = {cell["col"] for cell in cells}
                cells.extend(cell for cell in annotations[number] if cell["col"] not in present)
                next_row = next(pending, None)
            if skip is not None and number <= skip:
                return True
            cells.sort(key=lambda cell: cell["col"])
            return pipeline.consume(number, cells)

        data_top = max(top, skip + 1) if skip is not None else top
        opened.scan(target, replace(plan, cell_window=(left, data_top, right, bottom)), row_sink=consume)
        while next_row is not None and not pipeline.complete:
            pipeline.consume(next_row, annotations[next_row])
            next_row = next(pending, None)
        return opened.result(_render_query_result(*pipeline.finish()), "query")
