"""Main rendering iterators for the three densities (M2: plain only)."""

from __future__ import annotations

from collections.abc import Iterator

from ..core.models import ParsedPresentation, ShapeBlock

_MEDIA_PLACEHOLDERS = {
    "video": "[Video]",
    "audio": "[Audio]",
}

_PLAIN_TABLE_ROW_LIMIT = 10


def iter_plain(parsed: ParsedPresentation) -> Iterator[str]:
    """plain — pure text stream with slide separators."""
    yield "density=plain\n"
    for slide in parsed.slides:
        if slide["n"] > 1:
            yield "\n"
        yield f"=== Slide {slide['n']} ===\n"
        yield "\n\n".join(_plain_shape_text(shape) for shape in slide["shapes"])


def _plain_shape_text(shape: ShapeBlock) -> str:
    if shape["type"] == "text":
        return shape["text"]
    if shape["type"] == "picture":
        alt = shape.get("alt")
        return f"[Image: {alt}]" if alt else "[Image]"
    if shape["type"] == "media":
        return _MEDIA_PLACEHOLDERS.get(shape.get("kind", ""), "[Media]")
    if shape["type"] == "table":
        return _plain_table_text(shape)
    if shape["type"] == "chart":
        chart_type = shape.get("chartType")
        series_count = shape.get("seriesCount")
        if chart_type and series_count is not None:
            return f"[Chart: {chart_type}, {series_count} series]"
        return "[Chart]"
    if shape["type"] == "smartart":
        layout = shape.get("layoutType")
        node_count = shape.get("nodeCount")
        if layout and node_count is not None:
            return f"[SmartArt: {layout}, {node_count} nodes]"
        return "[SmartArt]"
    raise AssertionError(f"Unknown shape type: {shape['type']}")


def _plain_table_text(shape: ShapeBlock) -> str:
    rows = shape.get("rows", [])
    cols = max((len(row) for row in rows), default=0)
    if len(rows) > _PLAIN_TABLE_ROW_LIMIT:
        body = "\n".join("\t".join(row) for row in rows[:_PLAIN_TABLE_ROW_LIMIT])
        return f"{body}\n[Table truncated: {len(rows)} rows, {cols} cols]"
    return "\n".join("\t".join(row) for row in rows)
