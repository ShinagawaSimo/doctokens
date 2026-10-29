"""Render parsed document resources for direct lookup APIs."""

from __future__ import annotations

from collections.abc import Callable

from doctokens_core.output.resources import resource_document
from doctokens_core.output.xml import append, element

from ...model import ParsedDocument, TableBlock, TableRow
from ...model.enums import ResourceType
from ...model.traversal import document_blocks
from ..dtx_content import _append_controls
from ..dtx_runs import review_parent
from .charts import render_chart_resource
from .smartarts import render_smartart_resource


def render_resource(
    parsed_document: ParsedDocument,
    resource_type: ResourceType | str,
    resource_id: str | None = None,
    *,
    rows: str | None = None,
    columns: list[str] | None = None,
    aggregate: str | None = None,
    aggregate_column: str | None = None,
) -> list[str]:
    """Render a resource as self-defined output for LLM consumption."""
    resolved_type = ResourceType.parse(resource_type)
    if resolved_type.is_plural and resource_id is not None:
        raise ValueError("resource_id is only valid with a singular resource type")
    if not resolved_type.is_plural and resource_id is None:
        raise ValueError("resource_id is required with a singular resource type")

    if resolved_type in {ResourceType.IMAGES, ResourceType.IMAGE}:
        raise ValueError("use read_resource() for DOCX image bytes")
    if resolved_type in {ResourceType.CHARTS, ResourceType.CHART}:
        return _render_charts(parsed_document, resource_id)
    if resolved_type in {ResourceType.SMARTARTS, ResourceType.SMARTART}:
        return _render_smartarts(parsed_document, resource_id)

    if resolved_type is ResourceType.TABLES:
        return [
            _render_table_resource(table_id, segments, rows, columns, aggregate, aggregate_column)
            for table_id, segments in table_groups(parsed_document).items()
        ]

    if resolved_type is ResourceType.TABLE:
        assert resource_id is not None
        segments = table_groups(parsed_document).get(resource_id)
        if segments is None:
            return []
        return [
            _render_table_resource(
                resource_id,
                segments,
                rows,
                columns,
                aggregate,
                aggregate_column,
            )
        ]

    raise AssertionError("validated resource type was not handled")


def table_groups(parsed_document: ParsedDocument) -> dict[str, list[TableBlock]]:
    """Group top-level table segments by their stable logical table ID."""
    groups: dict[str, list[TableBlock]] = {}
    for block in document_blocks(parsed_document):
        if block["type"] != "table":
            continue
        groups.setdefault(block["tableId"], []).append(block)
    return groups


def _render_charts(parsed_document: ParsedDocument, resource_id: str | None) -> list[str]:
    rendered_resources: list[str] = []
    for chart in parsed_document.charts:
        if resource_id and chart.get("id") != resource_id:
            continue
        rendered_resources.append(render_chart_resource(chart))
    return rendered_resources


def _render_smartarts(parsed_document: ParsedDocument, resource_id: str | None) -> list[str]:
    rendered_resources: list[str] = []
    for smartart in parsed_document.smartarts:
        if resource_id and smartart.get("id") != resource_id:
            continue
        rendered_resources.append(render_smartart_resource(smartart))
    return rendered_resources


def _render_table_resource(
    table_id: str,
    segments: list[TableBlock],
    rows: str | None,
    columns: list[str] | None,
    aggregate: str | None,
    aggregate_column: str | None,
) -> str:
    all_rows = [row for segment in segments for row in segment["rows"]]
    node = element(
        "table", id=table_id, rows=len(all_rows), cols=max((segment["columnCount"] for segment in segments), default=0)
    )
    if aggregate is not None:
        result = _aggregate_rows(all_rows, aggregate, aggregate_column or "")
        append(node, "aggregate", str(result["aggregate_value"]), op=result["aggregate"], column=result["aggregate_column"])
    else:
        for row in _filter_and_slice_rows(all_rows, rows, columns):
            container = review_parent(_append_controls(node, row.get("contentControls", []), "semantic"), row, "semantic")
            child = append(
                container,
                "tr",
                isHeader=True if row.get("isHeader") else None,
                grid_before=row.get("gridBefore"),
                grid_after=row.get("gridAfter"),
            )
            next_column = row.get("gridBefore", 0)
            for cell in row["cells"]:
                container = review_parent(_append_controls(child, cell.get("contentControls", []), "semantic"), cell, "semantic")
                append(
                    container,
                    "td",
                    cell.get("text", ""),
                    column=cell["colIndex"] + 1 if cell["colIndex"] != next_column else None,
                    colspan=cell["colSpan"] if cell["colSpan"] != 1 else None,
                    rowspan=cell["rowSpan"] if cell["rowSpan"] != 1 else None,
                    v_merge=cell.get("vMerge"),
                    background=cell.get("background"),
                )
                next_column = cell["colIndex"] + cell["colSpan"]
    return resource_document("docx", node)


def _filter_and_slice_rows(
    rows: list[TableRow],
    rows_spec: str | None,
    columns: list[str] | None,
) -> list[TableRow]:
    if columns is not None:
        rows = _filter_columns(rows, columns)
    if rows_spec is not None:
        rows = _slice_rows(rows, rows_spec)
    return rows


def _slice_rows(rows: list[TableRow], spec: str) -> list[TableRow]:
    try:
        start_str, end_str = spec.split("-", 1)
        start = int(start_str) - 1
        end = int(end_str)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid rows range: {spec!r}") from None
    if start < 0 or end <= start:
        raise ValueError(f"Invalid rows range: {spec!r}")
    return rows[start:end]


def _filter_columns(rows: list[TableRow], column_names: list[str]) -> list[TableRow]:
    if not rows:
        return rows
    header = rows[0]
    keep_indices: set[int] = set()
    for name in column_names:
        for cell in header["cells"]:
            if cell["text"] == name:
                keep_indices.update(range(cell["colIndex"], cell["colIndex"] + cell["colSpan"]))
                break

    filtered_rows: list[TableRow] = []
    for row in rows:
        selected_cells = [
            cell
            for cell in row["cells"]
            if any(column in keep_indices for column in range(cell["colIndex"], cell["colIndex"] + cell["colSpan"]))
        ]
        filtered_row: TableRow = row.copy()
        filtered_row["cells"] = selected_cells
        filtered_rows.append(filtered_row)
    return filtered_rows


_AGGREGATORS: dict[str, Callable[[list[float]], float | int]] = {
    "sum": sum,
    "count": len,
    "avg": lambda vals: sum(vals) / len(vals) if vals else 0,
    "min": lambda vals: min(vals) if vals else 0,
    "max": lambda vals: max(vals) if vals else 0,
}


def _aggregate_rows(rows: list[TableRow], operation: str, column: str) -> dict[str, object]:
    operation = operation.lower()
    if operation not in _AGGREGATORS:
        raise ValueError(f"Unknown aggregate {operation!r}; expected one of: {', '.join(sorted(_AGGREGATORS))}")
    values = _numeric_column_values(rows, column)
    return {
        "aggregate": operation,
        "aggregate_column": column,
        "aggregate_value": _AGGREGATORS[operation](values),
    }


def _numeric_column_values(rows: list[TableRow], column: str) -> list[float]:
    if not rows:
        return []
    header = rows[0]
    col_idx: int | None = None
    for cell in header["cells"]:
        if cell["text"] == column:
            col_idx = cell["colIndex"]
            break
    if col_idx is None:
        raise ValueError(f"Column {column!r} not found in table header")

    values: list[float] = []
    for row in rows[1:]:
        matched_cell = next(
            (cell for cell in row["cells"] if cell["colIndex"] <= col_idx < cell["colIndex"] + cell["colSpan"]), None
        )
        if matched_cell is None:
            continue
        text = matched_cell.get("text", "").strip()
        if not text:
            continue
        try:
            values.append(float(text))
        except ValueError:
            continue
    return values
