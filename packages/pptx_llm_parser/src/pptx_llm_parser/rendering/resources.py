"""Resource output rendering with lazy binary access and full object records."""

from __future__ import annotations

import base64
import re

from ooxml_llm_core.doctokens_xml import append, element
from ooxml_llm_core.resource_xml import resource_document

from ..core.enums import ResourceType
from ..core.models import ParsedPresentation
from ..core.package import PackageReader

_AGGREGATE_OPS = {"sum", "count", "avg", "min", "max"}


def render_resource(
    parsed_presentation: ParsedPresentation,
    package_reader: PackageReader | None,
    resource_type: ResourceType,
    resource_id: str,
    *,
    rows: str | None = None,
    columns: list[int] | None = None,
    aggregate: str | None = None,
    aggregate_column: int | None = None,
) -> str | None:
    if resource_type == ResourceType.IMAGE:
        return _render_asset(parsed_presentation, package_reader, resource_id, "image")
    if resource_type == ResourceType.MEDIA:
        return _render_asset(parsed_presentation, package_reader, resource_id, "media")
    if resource_type == ResourceType.CHART:
        return _render_chart(parsed_presentation, resource_id)
    if resource_type == ResourceType.SMARTART:
        return _render_smartart(parsed_presentation, resource_id)
    if resource_type == ResourceType.TABLE:
        return _render_table(parsed_presentation, resource_id, rows, columns, aggregate, aggregate_column)
    return None


def _render_asset(
    parsed_presentation: ParsedPresentation,
    package_reader: PackageReader | None,
    resource_id: str,
    asset_type: str,
) -> str | None:
    asset = next(
        (asset for asset in parsed_presentation.assets if asset["id"] == resource_id and asset["type"] == asset_type),
        None,
    )
    if asset is None or asset.get("source") != "embedded" or package_reader is None:
        return None
    zip_path = asset.get("zipPath")
    if zip_path is None or not package_reader.exists(zip_path):
        return None
    with package_reader.open_entry(zip_path) as entry_stream:
        asset_bytes = entry_stream.read()
    return base64.b64encode(asset_bytes).decode("ascii")


def _render_chart(parsed_presentation: ParsedPresentation, resource_id: str) -> str | None:
    chart = next((chart for chart in parsed_presentation.charts if chart.get("id") == resource_id), None)
    if chart is None:
        return None
    chart_type = chart.get("chart_type")
    title = chart.get("title")
    series = chart.get("series", [])
    point_count = chart.get("point_count")
    plots = chart.get("plots", [])
    is_combination = chart_type == "combination"
    node = element(
        "chart",
        id=resource_id,
        type=chart_type or None,
        title=title or None,
        series=len(series),
        points=point_count if point_count is not None else 0,
        plots=",".join(plot.get("chart_type", "unknown") for plot in plots) if is_combination and plots else None,
    )
    for series_index, series_item in enumerate(series, start=1):
        append(
            node,
            "series",
            id=series_index,
            name=series_item.get("name") or None,
            categories=",".join(series_item.get("categories", [])),
            values=",".join(series_item.get("values", [])),
            type=series_item.get("chart_type") if is_combination else None,
            bubbleSizes=",".join(series_item["bubble_sizes"]) if series_item.get("bubble_sizes") else None,
            xValues=",".join(series_item["x_values"]) if series_item.get("x_values") else None,
            yValues=",".join(series_item["y_values"]) if series_item.get("y_values") else None,
            hidden=True if series_item.get("hidden") else None,
            min=f"{series_item['min']:g}" if series_item.get("min") is not None else None,
            max=f"{series_item['max']:g}" if series_item.get("max") is not None else None,
        )
    return resource_document("pptx", node)


def _render_smartart(parsed_presentation: ParsedPresentation, resource_id: str) -> str | None:
    smartart_record = next(
        (record for record in parsed_presentation.smartarts if record.get("id") == resource_id),
        None,
    )
    if smartart_record is None:
        return None
    layout_type: str | None = smartart_record.get("layoutType")
    for slide in parsed_presentation.slides:
        for shape in slide["shapes"]:
            if shape["type"] == "smartart" and shape.get("smartartId") == resource_id:
                layout_type = shape.get("layoutType")
                break
        if layout_type:
            break
    nodes = smartart_record.get("nodes", [])
    links = smartart_record.get("links", [])
    root = element("smartart", id=resource_id, type=layout_type, nodes=len(nodes), links=len(links))
    for node in nodes:
        append(root, "node", node["text"], id=node["id"])
    for link in links:
        append(root, "link", **{"from": link["from"], "to": link["to"]})
    return resource_document("pptx", root)


def _render_table(
    parsed_presentation: ParsedPresentation,
    resource_id: str,
    rows: str | None,
    columns: list[int] | None,
    aggregate: str | None,
    aggregate_column: int | None,
) -> str | None:
    if aggregate is not None and aggregate not in _AGGREGATE_OPS:
        raise ValueError(f"aggregate must be one of: {', '.join(sorted(_AGGREGATE_OPS))}")
    if aggregate is not None and aggregate_column is None:
        raise ValueError("aggregate_column is required when aggregate is set")
    if aggregate is None and aggregate_column is not None:
        raise ValueError("aggregate is required when aggregate_column is set")
    if aggregate_column is not None and (
        isinstance(aggregate_column, bool) or not isinstance(aggregate_column, int) or aggregate_column < 0
    ):
        raise ValueError("aggregate_column must be a non-negative integer")
    if columns is not None and any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in columns):
        raise ValueError("columns must contain non-negative integers")
    table_shape = None
    for slide in parsed_presentation.slides:
        for candidate in slide["shapes"]:
            if candidate["type"] == "table" and candidate.get("tableId") == resource_id:
                table_shape = candidate
                break
        if table_shape is not None:
            break
    if table_shape is None:
        return None
    table_rows = table_shape.get("rows", [])
    start_index, end_index = _parse_rows_spec(rows, len(table_rows))
    selected_rows = table_rows[start_index:end_index]
    aggregate_rows = selected_rows
    if columns is not None:
        selected_rows = [[row[column_index] for column_index in columns if column_index < len(row)] for row in selected_rows]
    column_count = max((len(row) for row in selected_rows), default=0)
    node = element("table", id=resource_id, rows=len(selected_rows), cols=column_count)
    for row in selected_rows:
        child = append(node, "tr")
        for cell in row:
            append(child, "td", cell)
    if aggregate is not None and aggregate_column is not None:
        values = _numeric_cells(aggregate_rows, aggregate_column)
        append(node, "aggregate", op=aggregate, column=aggregate_column, value=f"{_aggregate(aggregate, values):g}")
    return resource_document("pptx", node)


def _parse_rows_spec(spec: str | None, row_count: int) -> tuple[int, int]:
    if spec is None:
        return 0, row_count
    match = re.fullmatch(r"([1-9]\d*)(?:-([1-9]\d*))?", spec)
    if match is None:
        raise ValueError(f"Invalid rows spec: {spec!r}")
    start = int(match.group(1)) - 1
    end = int(match.group(2) or match.group(1))
    if start >= row_count or end <= start or end > row_count:
        raise ValueError(f"Invalid rows spec: {spec!r}")
    return start, end


def _numeric_cells(rows: list[list[str]], column: int) -> list[float]:
    numeric_values: list[float] = []
    for row in rows:
        if column < len(row):
            try:
                numeric_values.append(float(row[column]))
            except ValueError:
                continue
    return numeric_values


def _aggregate(op: str, values: list[float]) -> float:
    if op == "count":
        return float(len(values))
    if not values:
        return 0.0
    if op == "sum":
        return sum(values)
    if op == "avg":
        return sum(values) / len(values)
    if op == "min":
        return min(values)
    return max(values)
