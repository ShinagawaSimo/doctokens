"""Query helpers for parsed XLSX table and range data."""

from __future__ import annotations

from collections.abc import Iterator

from doctokens_core.output.resources import operation_root
from doctokens_core.output.xml import append, serialize

from ..model.workbook import Cell, ParsedWorkbook, SheetInfo
from ..rendering.selection import find_sheet, parse_range
from .columns import _columns_from_header, _columns_from_labels
from .pipeline import QueryPipeline
from .types import AggregateSpec as AggregateSpec
from .types import OrderSpec as OrderSpec
from .types import QueryColumn as QueryColumn
from .types import WhereCondition as WhereCondition


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
    if not query_columns and header_row is not None and start_row <= header_row <= end_row:
        header = next((row for row in query_sheet.get("rows", []) if row and row[0]["row"] == header_row), None)
        if header is not None:
            query_columns = _columns_from_header(header, start_col, end_col)
    pipeline = QueryPipeline(
        query_columns, where=where, group_by=group_by, aggregates=aggregates, select=select, order_by=order_by, limit=limit
    )
    for cells in _rows_in_range(query_sheet, start_row, end_row):
        row_number = cells[0]["row"]
        if header_row_to_skip is not None and row_number <= header_row_to_skip:
            continue
        selected = [cell for cell in cells if start_col <= cell["col"] <= end_col]
        if selected and not pipeline.consume(row_number, selected):
            break
    return _render_query_result(*pipeline.finish())


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
                    bounds = parse_range(table["ref"])
                    start_col, _start_row, end_col, _end_row = bounds
                    table_columns = [str(item) for item in table.get("columns", [])]
                    columns = _columns_from_labels(table_columns, start_col, end_col)
                    return sheet_info, columns, bounds, bounds[1]
        raise ValueError(f"Table {table_id!r} not found")

    if sheet is not None and range_spec is not None and header_row is not None:
        sheet_info = find_sheet(parsed_workbook, sheet)
        return sheet_info, [], parse_range(range_spec), header_row

    raise ValueError("Provide table_id or (sheet + range_spec + header_row)")


def _rows_in_range(
    sheet_obj: SheetInfo,
    start_row: int,
    end_row: int,
) -> Iterator[list[Cell]]:
    for row_cells in sheet_obj.get("rows", []):
        if not row_cells:
            continue
        row_num = row_cells[0]["row"]
        if row_num < start_row:
            continue
        if row_num > end_row:
            break
        yield row_cells


def _render_query_result(rows: list[dict[str, object]], columns: list[QueryColumn] | None = None) -> str:
    root = operation_root("xlsx", "structural")
    table = append(append(root, "query"), "table")
    if rows:
        all_cols: list[QueryColumn]
        all_cols = (
            [{"key": col, "label": col, "col": 0} for col in rows[0] if col != "__row"]
            if columns is None
            else [col for col in columns if any(col["key"] in row for row in rows)]
        )
        header = append(table, "tr")
        for column in all_cols:
            append(header, "th", column["label"])
        for row in rows:
            child = append(table, "tr")
            for column in all_cols:
                append(child, "td", str(row.get(column["key"], "")))
    return serialize(root)
