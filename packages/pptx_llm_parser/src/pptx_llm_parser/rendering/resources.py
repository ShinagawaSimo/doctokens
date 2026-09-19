"""Resource output rendering with lazy binary access and full object records."""

from __future__ import annotations

import base64
import re
from html import escape as escape_text

from ..core.enums import ResourceType
from ..core.models import ParsedPresentation
from ..core.package import PackageReader
from .markup import AttributeBuilder

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
    attrs = AttributeBuilder().add("id", resource_id)
    chart_type = chart.get("chart_type")
    if chart_type:
        attrs.add("type", chart_type)
    title = chart.get("title")
    if title:
        attrs.add("title", title)
    series = chart.get("series", [])
    point_count = chart.get("point_count")
    attrs.add("series", len(series)).add("points", point_count if point_count is not None else 0)
    plots = chart.get("plots", [])
    is_combination = chart_type == "combination"
    if is_combination and plots:
        attrs.add("plots", ",".join(plot.get("chart_type", "unknown") for plot in plots))
    output_lines = [f"<chart{attrs.render()}>"]
    for series_index, series_item in enumerate(series, start=1):
        series_attrs = AttributeBuilder().add("id", series_index)
        series_name = series_item.get("name")
        if series_name:
            series_attrs.add("name", series_name)
        series_attrs.add("categories", ",".join(series_item.get("categories", [])))
        series_attrs.add("values", ",".join(series_item.get("values", [])))
        if is_combination and series_item.get("chart_type"):
            series_attrs.add("type", series_item["chart_type"])
        if series_item.get("bubble_sizes"):
            series_attrs.add("bubbleSizes", ",".join(series_item["bubble_sizes"]))
        if series_item.get("hidden"):
            series_attrs.flag("hidden")
        if series_item.get("x_values"):
            series_attrs.add("xValues", ",".join(series_item["x_values"]))
        if series_item.get("y_values"):
            series_attrs.add("yValues", ",".join(series_item["y_values"]))
        if series_item.get("min") is not None:
            series_attrs.add("min", f"{series_item['min']:g}")
        if series_item.get("max") is not None:
            series_attrs.add("max", f"{series_item['max']:g}")
        output_lines.append(f"<series{series_attrs.render()}>")
    return "\n".join(output_lines)


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
    attrs = AttributeBuilder().add("id", resource_id).add("type", layout_type).add("nodes", len(nodes)).add("links", len(links))
    output_lines = [f"<smartart{attrs.render()}>"]
    output_lines.extend(f"<node{AttributeBuilder().add('id', node['id']).render()}>{escape_text(node['text'])}" for node in nodes)
    output_lines.extend(f"<link{AttributeBuilder().add('from', link['from']).add('to', link['to']).render()}>" for link in links)
    return "\n".join(output_lines)


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
    attrs = AttributeBuilder().add("id", resource_id).add("rows", len(selected_rows)).add("cols", column_count)
    output_lines = [f"<table{attrs.render()}>"]
    for row in selected_rows:
        cells = "".join(f"<td>{escape_text(cell)}</td>" for cell in row)
        output_lines.append(f"<tr>{cells}")
    if aggregate is not None and aggregate_column is not None:
        values = _numeric_cells(aggregate_rows, aggregate_column)
        attrs = (
            AttributeBuilder()
            .add("op", aggregate)
            .add("column", aggregate_column)
            .add("value", f"{_aggregate(aggregate, values):g}")
        )
        output_lines.append(f"<aggregate{attrs.render()}>")
    return "\n".join(output_lines)


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
