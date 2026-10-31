"""Plain PPTX output pipeline."""

from __future__ import annotations

from collections.abc import Iterator

from doctokens_core.ooxml.charts.preview import plain_chart
from doctokens_core.runtime.execution import checkpoint

from ..model.presentation import ChartRecord, ParsedPresentation, ShapeBlock, SlideBlock, SmartArtRecord
from .diagrams import diagram_text

_MEDIA_PLACEHOLDERS = {"video": "[Video]", "audio": "[Audio]"}
_TABLE_ROW_LIMIT = 10


def iter_plain(parsed_presentation: ParsedPresentation) -> Iterator[str]:
    """Render the deliberately unformatted presentation text stream."""
    smartarts = {item["id"]: item for item in parsed_presentation.smartarts}
    charts = {item["id"]: item for item in parsed_presentation.charts}
    for slide in parsed_presentation.slides:
        checkpoint("rendering PPTX slides")
        if slide["n"] > 1:
            yield "\n"
        section = slide.get("section")
        label = f" (Section: {section})" if section else ""
        yield f"=== Slide {slide['n']}{label} ===\n"
        yield _slide_body(slide, smartarts, charts)
    if parsed_presentation.comments:
        yield "\n\n[Comments]\n"
        yield "\n".join(
            f"[comment status={item.get('status', 'unknown')}] {item['text']}".rstrip() for item in parsed_presentation.comments
        )


def _slide_body(slide: SlideBlock, smartarts: dict[str, SmartArtRecord], charts: dict[str, ChartRecord]) -> str:
    values = [value for shape in slide["shapes"] if (value := _shape_text(shape, smartarts, charts))]
    if slide["notes"]:
        values.append(f"[Notes: {slide['notes']}]")
    return "\n\n".join(values)


def _shape_text(shape: ShapeBlock, smartarts: dict[str, SmartArtRecord], charts: dict[str, ChartRecord]) -> str:
    if shape["type"] == "unsupported":
        return f"[Unparsed shape: {shape.get('sourceKind', 'shape')}]"
    if shape["type"] == "text":
        if paragraphs := shape.get("paragraphs"):
            lines = []
            for paragraph in paragraphs:
                indent = "  " * max(0, min(8, paragraph.get("level", 0)))
                lines.append(indent + paragraph.get("text", "").replace("\n", "\n" + indent))
            return "\n".join(lines)
        return shape["text"]
    if shape["type"] == "picture":
        poster = f"[Image: {shape['alt']}]" if shape.get("alt") else "[Image]"
        if shape.get("embeddedType"):
            poster = f"[OLE preview: {shape['embeddedType']}]"
        if shape.get("mediaKind"):
            return poster + "\n\n" + _MEDIA_PLACEHOLDERS.get(shape["mediaKind"], "[Media]")
        return poster
    if shape["type"] == "media":
        return _MEDIA_PLACEHOLDERS.get(shape.get("kind", ""), "[Media]")
    if shape["type"] == "table":
        rows = shape.get("rows", [])
        columns = max((len(row) for row in rows), default=0)
        visible_rows = rows[:_TABLE_ROW_LIMIT]
        body = "\n".join("\t".join(row) for row in visible_rows)
        return f"{body}\n[Table truncated: {len(rows)} rows, {columns} cols]" if len(rows) > _TABLE_ROW_LIMIT else body
    if shape["type"] == "chart":
        chart_record = charts.get(shape.get("chartId", ""))
        if chart_record is None:
            return "[Unparsed chart]"
        return plain_chart(
            shape.get("chartId"),
            shape.get("chartType", "?"),
            shape.get("chartTitle"),
            [item["name"] for item in chart_record.get("series", []) if item.get("name")] if chart_record else [],
            shape.get("seriesCount", 0),
        )
    if shape["type"] == "smartart":
        record = smartarts.get(shape.get("smartartId", ""))
        return diagram_text(record) if record is not None else "[Unparsed SmartArt]"
    if shape["type"] == "shape":
        if description := shape.get("alt") or shape.get("title"):
            return f"[Shape: {description}]"
        if shape.get("link"):
            return "[Linked shape]"
        return "[Connector]" if shape.get("kind") == "connector" else ""
    raise AssertionError(f"Unknown shape type: {shape['type']}")


__all__ = ["iter_plain"]
