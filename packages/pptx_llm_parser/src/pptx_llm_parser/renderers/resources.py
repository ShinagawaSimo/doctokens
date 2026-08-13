"""get_resource rendering — lazy binary (base64) + full object records."""

from __future__ import annotations

import base64
from html import escape

from ..core.enums import ResourceType
from ..core.models import ParsedPresentation
from ..core.package import PackageReader

_AGGREGATE_OPS = {"sum", "count", "avg", "min", "max"}


def render_resource(
    parsed: ParsedPresentation,
    pkg: PackageReader | None,
    resource_type: ResourceType,
    resource_id: str,
    *,
    rows: str | None = None,
    columns: list[int] | None = None,
    aggregate: str | None = None,
    aggregate_column: int | None = None,
) -> str | None:
    if resource_type == ResourceType.IMAGE:
        return _render_asset(parsed, pkg, resource_id, "image")
    if resource_type == ResourceType.MEDIA:
        return _render_asset(parsed, pkg, resource_id, "media")
    if resource_type == ResourceType.CHART:
        return _render_chart(parsed, resource_id)
    if resource_type == ResourceType.SMARTART:
        return _render_smartart(parsed, resource_id)
    if resource_type == ResourceType.TABLE:
        return _render_table(parsed, resource_id, rows, columns, aggregate, aggregate_column)
    return None


def _render_asset(
    parsed: ParsedPresentation,
    pkg: PackageReader | None,
    resource_id: str,
    asset_type: str,
) -> str | None:
    asset = next((a for a in parsed.assets if a["id"] == resource_id and a["type"] == asset_type), None)
    if asset is None or asset.get("source") != "embedded" or pkg is None:
        return None
    zip_path = asset.get("zipPath")
    if zip_path is None or not pkg.exists(zip_path):
        return None
    with pkg.open_entry(zip_path) as stream:
        raw = stream.read()
    return base64.b64encode(raw).decode("ascii")


def _render_chart(parsed: ParsedPresentation, resource_id: str) -> str | None:
    chart = next((c for c in parsed.charts if c.get("id") == resource_id), None)
    if chart is None:
        return None
    parts = [f"<chart id={resource_id}"]
    chart_type = chart.get("chart_type")
    if chart_type:
        parts.append(f" type={chart_type}")
    title = chart.get("title")
    if title:
        parts.append(f" title={escape(title)}")
    series = chart.get("series", [])
    point_count = chart.get("point_count")
    parts.append(f" series={len(series)} points={point_count if point_count is not None else 0}>")
    lines = ["".join(parts)]
    for index, item in enumerate(series, start=1):
        line = [f"<series id={index}"]
        name = item.get("name")
        if name:
            line.append(f" name={escape(name)}")
        line.append(f" categories={','.join(escape(c) for c in item.get('categories', []))}")
        line.append(f" values={','.join(item.get('values', []))}")
        if item.get("min") is not None:
            line.append(f" min={item['min']:g}")
        if item.get("max") is not None:
            line.append(f" max={item['max']:g}")
        line.append(">")
        lines.append("".join(line))
    return "\n".join(lines)


def _render_smartart(parsed: ParsedPresentation, resource_id: str) -> str | None:
    record = next((s for s in parsed.smartarts if s.get("id") == resource_id), None)
    if record is None:
        return None
    layout: str | None = None
    for slide in parsed.slides:
        for shape in slide["shapes"]:
            if shape["type"] == "smartart" and shape.get("smartartId") == resource_id:
                layout = shape.get("layoutType")
                break
        if layout:
            break
    parts = [f"<smartart id={resource_id}"]
    if layout:
        parts.append(f" type={layout}")
    nodes = record.get("nodes", [])
    links = record.get("links", [])
    parts.append(f" nodes={len(nodes)} links={len(links)}>")
    lines = ["".join(parts)]
    lines.extend(f"<node id={node['id']}>{escape(node['text'])}" for node in nodes)
    lines.extend(f"<link from={link['from']} to={link['to']}>" for link in links)
    return "\n".join(lines)


def _render_table(
    parsed: ParsedPresentation,
    resource_id: str,
    rows: str | None,
    columns: list[int] | None,
    aggregate: str | None,
    aggregate_column: int | None,
) -> str | None:
    if aggregate is not None and aggregate not in _AGGREGATE_OPS:
        raise ValueError(f"aggregate must be one of: {', '.join(sorted(_AGGREGATE_OPS))}")
    shape = None
    for slide in parsed.slides:
        for candidate in slide["shapes"]:
            if candidate["type"] == "table" and candidate.get("tableId") == resource_id:
                shape = candidate
                break
        if shape is not None:
            break
    if shape is None:
        return None
    table_rows = shape.get("rows", [])
    start, end = _parse_rows_spec(rows, len(table_rows))
    selected = table_rows[start:end]
    if columns is not None:
        selected = [[row[i] for i in columns if i < len(row)] for row in selected]
    cols = max((len(row) for row in selected), default=0)
    lines = [f"<table id={resource_id} rows={len(selected)} cols={cols}>"]
    for row in selected:
        cells = "".join(f"<td>{escape(cell)}</td>" for cell in row)
        lines.append(f"<tr>{cells}")
    if aggregate is not None and aggregate_column is not None:
        values = _numeric_cells(selected, aggregate_column)
        lines.append(f"<aggregate op={aggregate} column={aggregate_column} value={_aggregate(aggregate, values):g}>")
    return "\n".join(lines)


def _parse_rows_spec(spec: str | None, row_count: int) -> tuple[int, int]:
    if spec is None:
        return 0, row_count
    if "-" in spec:
        first, _, last = spec.partition("-")
        start = int(first) - 1
        end = int(last)
    else:
        start = int(spec) - 1
        end = start + 1
    if start < 0 or end < start or start > row_count:
        raise ValueError(f"Invalid rows spec: {spec!r}")
    return start, end


def _numeric_cells(rows: list[list[str]], column: int) -> list[float]:
    values: list[float] = []
    for row in rows:
        if column < len(row):
            try:
                values.append(float(row[column]))
            except ValueError:
                continue
    return values


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
