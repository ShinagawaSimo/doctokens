"""Render parsed document resources for direct lookup APIs."""

from __future__ import annotations

import base64
import zipfile
from collections.abc import Callable

from ..core.enums import ResourceType
from ..core.models import ParsedDocument, ResourceDetail, TableBlock, TableRow
from .objects import render_chart_resource, render_smartart_resource


def render_resource(
    parsed: ParsedDocument,
    resource_type: ResourceType | str,
    resource_id: str | None = None,
    *,
    rows: str | None = None,
    columns: list[str] | None = None,
    aggregate: str | None = None,
    aggregate_column: str | None = None,
) -> list[str]:
    """Render a resource as an HTML string for LLM consumption."""
    resolved_type = ResourceType.parse(resource_type)
    if resolved_type.is_plural and resource_id is not None:
        raise ValueError("resource_id is only valid with a singular resource type")
    if not resolved_type.is_plural and resource_id is None:
        raise ValueError("resource_id is required with a singular resource type")

    if resolved_type in {ResourceType.IMAGES, ResourceType.IMAGE}:
        return _render_images(parsed, resource_id)
    if resolved_type in {ResourceType.CHARTS, ResourceType.CHART}:
        return _render_charts(parsed, resource_id)
    if resolved_type in {ResourceType.SMARTARTS, ResourceType.SMARTART}:
        return _render_smartarts(parsed, resource_id)

    if resolved_type is ResourceType.TABLES:
        return [
            _render_table_resource(table_id, segments, rows, columns, aggregate, aggregate_column)
            for table_id, segments in table_groups(parsed).items()
        ]

    if resolved_type is ResourceType.TABLE:
        assert resource_id is not None
        segments = table_groups(parsed).get(resource_id)
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


def table_groups(parsed: ParsedDocument) -> dict[str, list[TableBlock]]:
    """Group top-level table segments by their stable logical table ID."""
    groups: dict[str, list[TableBlock]] = {}
    for block in parsed.blocks:
        if block["type"] != "table":
            continue
        groups.setdefault(block["tableId"], []).append(block)
    return groups


def _render_images(parsed: ParsedDocument, resource_id: str | None) -> list[str]:
    source_path = parsed.metadata.get("sourcePath")
    ocr = getattr(parsed, "ocr_results", None) or {}
    result: list[str] = []
    for asset in parsed.assets:
        if resource_id and asset["id"] != resource_id:
            continue
        attrs = f"id={asset['id']}"
        if asset.get("href"):
            attrs += f" href={asset['href']}"
        if asset.get("contentType"):
            attrs += f" contentType={asset['contentType']}"
        parts = [f"<image {attrs}>"]
        zip_path = asset.get("zipPath")
        if zip_path and isinstance(source_path, str) and source_path:
            with zipfile.ZipFile(source_path, "r") as zf:
                data = zf.read(zip_path)
            parts.append(base64.b64encode(data).decode())
        ocr_text = ocr.get(asset["id"])
        if ocr_text is not None:
            parts.append(f"\n<ocr-text id={asset['id']}>{ocr_text}")
        result.append("".join(parts))
    return result


def _render_charts(parsed: ParsedDocument, resource_id: str | None) -> list[str]:
    result: list[str] = []
    for chart in parsed.charts:
        if resource_id and chart.get("id") != resource_id:
            continue
        result.append(render_chart_resource(chart))
    return result


def _render_smartarts(parsed: ParsedDocument, resource_id: str | None) -> list[str]:
    result: list[str] = []
    for smartart in parsed.smartarts:
        if resource_id and smartart.get("id") != resource_id:
            continue
        result.append(render_smartart_resource(smartart))
    return result


def _render_table_resource(
    table_id: str,
    segments: list[TableBlock],
    rows: str | None,
    columns: list[str] | None,
    aggregate: str | None,
    aggregate_column: str | None,
) -> str:
    all_rows = [row for segment in segments for row in segment["rows"]]
    column_count = max((seg["columnCount"] for seg in segments), default=0)
    attrs = f"id={table_id} rows={len(all_rows)} cols={column_count}"
    parts = [f"<table {attrs}>"]

    if aggregate is not None:
        agg_result = _compute_aggregate(all_rows, aggregate, aggregate_column or "")
        op = agg_result.get("aggregate", "")
        col = agg_result.get("aggregate_column", "")
        val = agg_result.get("aggregate_value", "")
        parts.append(f"\n<aggregate op={op} column={col}>{val}")
    else:
        filtered = _slice_and_filter_rows(all_rows, rows, columns)
        for row in filtered:
            cells = "|".join(cell.get("text", "") for cell in row["cells"])
            if row.get("isHeader"):
                parts.append(f"\n<tr isHeader>{cells}")
            else:
                parts.append(f"\n<tr>{cells}")
    return "".join(parts)


def _slice_and_filter_rows(
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
    if start < 0 or end < start:
        raise ValueError(f"Invalid rows range: {spec!r}")
    return rows[start:end]


def _filter_columns(rows: list[TableRow], column_names: list[str]) -> list[TableRow]:
    if not rows:
        return rows
    header = rows[0]
    header_texts = [cell["text"] for cell in header["cells"]]
    keep_indices: list[int] = []
    for name in column_names:
        for idx, hdr_text in enumerate(header_texts):
            if hdr_text == name and idx not in keep_indices:
                keep_indices.append(idx)
                break
    keep_indices.sort()

    result: list[TableRow] = []
    for row in rows:
        filtered = [row["cells"][i] for i in keep_indices if i < len(row["cells"])]
        filtered_row: TableRow = {"rowIndex": row["rowIndex"], "cells": filtered}
        if row.get("isHeader"):
            filtered_row["isHeader"] = True
        result.append(filtered_row)
    return result


_AGGREGATORS: dict[str, Callable[[list[float]], float | int]] = {
    "sum": sum,
    "count": len,
    "avg": lambda vals: sum(vals) / len(vals) if vals else 0,
    "min": lambda vals: min(vals) if vals else 0,
    "max": lambda vals: max(vals) if vals else 0,
}


def _compute_aggregate(rows: list[TableRow], operation: str, column: str) -> ResourceDetail:
    operation = operation.lower()
    if operation not in _AGGREGATORS:
        raise ValueError(f"Unknown aggregate {operation!r}; expected one of: {', '.join(sorted(_AGGREGATORS))}")
    values = _column_values(rows, column)
    return {
        "aggregate": operation,
        "aggregate_column": column,
        "aggregate_value": _AGGREGATORS[operation](values),
    }


def _column_values(rows: list[TableRow], column: str) -> list[float]:
    if not rows:
        return []
    header = rows[0]
    col_idx: int | None = None
    for idx, cell in enumerate(header["cells"]):
        if cell["text"] == column:
            col_idx = idx
            break
    if col_idx is None:
        raise ValueError(f"Column {column!r} not found in table header")

    values: list[float] = []
    for row in rows[1:]:
        if col_idx >= len(row["cells"]):
            continue
        text = row["cells"][col_idx].get("text", "").strip()
        if not text:
            continue
        try:
            values.append(float(text))
        except ValueError:
            continue
    return values
