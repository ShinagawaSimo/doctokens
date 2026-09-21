"""Plain PPTX output pipeline."""

from __future__ import annotations

from collections.abc import Iterator

from ..core.models import ParsedPresentation, ShapeBlock, SlideBlock

_MEDIA_PLACEHOLDERS = {"video": "[Video]", "audio": "[Audio]"}
_TABLE_ROW_LIMIT = 10


def iter_plain(parsed_presentation: ParsedPresentation) -> Iterator[str]:
    """Render the deliberately unformatted presentation text stream."""
    yield "density=plain\n"
    for slide in parsed_presentation.slides:
        if slide["n"] > 1:
            yield "\n"
        section = slide.get("section")
        label = f" (Section: {section})" if section else ""
        yield f"=== Slide {slide['n']}{label} ===\n"
        yield _slide_body(slide)
    if parsed_presentation.comments:
        yield "\n\n[Comments]\n"
        yield "\n".join(f"[{item['id']}: {item['text']}]" for item in parsed_presentation.comments)


def _slide_body(slide: SlideBlock) -> str:
    values = [value for shape in slide["shapes"] if (value := _shape_text(shape))]
    if slide["notes"]:
        values.append(f"[Notes: {slide['notes']}]")
    return "\n\n".join(values)


def _shape_text(shape: ShapeBlock) -> str:
    if shape["type"] == "text":
        return shape["text"]
    if shape["type"] == "picture":
        return f"[Image: {shape['alt']}]" if shape.get("alt") else "[Image]"
    if shape["type"] == "media":
        return _MEDIA_PLACEHOLDERS.get(shape.get("kind", ""), "[Media]")
    if shape["type"] == "table":
        rows = shape.get("rows", [])
        columns = max((len(row) for row in rows), default=0)
        visible_rows = rows[:_TABLE_ROW_LIMIT]
        body = "\n".join("\t".join(row) for row in visible_rows)
        return f"{body}\n[Table truncated: {len(rows)} rows, {columns} cols]" if len(rows) > _TABLE_ROW_LIMIT else body
    if shape["type"] == "chart":
        if shape.get("chartType") and shape.get("seriesCount") is not None:
            return f"[Chart: {shape['chartType']}, {shape['seriesCount']} series]"
        return "[Chart]"
    if shape["type"] == "smartart":
        if shape.get("layoutType") and shape.get("nodeCount") is not None:
            return f"[SmartArt: {shape['layoutType']}, {shape['nodeCount']} nodes]"
        return "[SmartArt]"
    if shape["type"] == "shape":
        if description := shape.get("alt") or shape.get("title"):
            return f"[Shape: {description}]"
        if shape.get("link"):
            return "[Linked shape]"
        return "[Connector]" if shape.get("kind") == "connector" else ""
    raise AssertionError(f"Unknown shape type: {shape['type']}")


__all__ = ["iter_plain"]
