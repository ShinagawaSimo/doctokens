"""Main rendering iterators for the three densities."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from html import escape

from ..core.models import CommentItem, OcrStoredResult, ParsedPresentation, ShapeBlock, SlideBlock, SmartArtRecord
from ._ocr import render_ocr_result
from .markup import AttributeBuilder

_MEDIA_PLACEHOLDERS = {
    "video": "[Video]",
    "audio": "[Audio]",
}

_PLAIN_TABLE_ROW_LIMIT = 10
_STRUCTURAL_TABLE_ROW_LIMIT = 30
_TITLE_PH_TYPES = {"title", "ctrTitle"}


def iter_plain(parsed: ParsedPresentation) -> Iterator[str]:
    """plain — pure text stream with slide separators."""
    yield "density=plain\n"
    for slide in parsed.slides:
        if slide["n"] > 1:
            yield "\n"
        yield f"=== Slide {slide['n']} ===\n"
        yield _plain_slide_body(slide)
    comments = _plain_comments_block(parsed)
    if comments:
        yield comments


def _plain_slide_body(slide: SlideBlock) -> str:
    parts = [_plain_shape_text(shape) for shape in slide["shapes"]]
    if slide["notes"]:
        parts.append(f"[Notes: {slide['notes']}]")
    return "\n\n".join(parts)


def _plain_comments_block(parsed: ParsedPresentation) -> str:
    if not parsed.comments:
        return ""
    lines = ["[Comments]"]
    lines.extend(f"[{comment['id']}: {comment['text']}]" for comment in parsed.comments)
    return "\n\n" + "\n".join(lines)


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
    if shape["type"] == "shape":
        return ""
    raise AssertionError(f"Unknown shape type: {shape['type']}")


def _plain_table_text(shape: ShapeBlock) -> str:
    rows = shape.get("rows", [])
    cols = max((len(row) for row in rows), default=0)
    if len(rows) > _PLAIN_TABLE_ROW_LIMIT:
        body = "\n".join("\t".join(row) for row in rows[:_PLAIN_TABLE_ROW_LIMIT])
        return f"{body}\n[Table truncated: {len(rows)} rows, {cols} cols]"
    return "\n".join("\t".join(row) for row in rows)


def iter_structural(parsed: ParsedPresentation) -> Iterator[str]:
    """structural — block structure + semantic objects, no visual formats."""
    yield "density=structural\n"
    smartart_nodes = {smartart["id"]: smartart for smartart in parsed.smartarts}
    for slide in parsed.slides:
        yield _html_slide_block(slide, smartart_nodes, semantic=False)
    comments = _html_comments_block(parsed)
    if comments:
        yield comments


def _html_slide_block(
    slide: SlideBlock,
    smartart_nodes: dict[str, SmartArtRecord],
    *,
    semantic: bool,
    ocr_results: Mapping[str, OcrStoredResult] | None = None,
) -> str:
    line_fn = _semantic_shape_line if semantic else _structural_shape_line
    lines = [_slide_open(slide).rstrip("\n")]
    for reference in slide.get("commentRefs", []):
        attrs = AttributeBuilder().add("id", reference["id"]).add("shape", reference.get("shapeId"))
        lines.append(f"<commentref{attrs.render()}>")
    background = slide.get("background")
    if semantic and background is not None:
        asset_id = background.get("assetId")
        if asset_id:
            rendered_ocr = render_ocr_result(asset_id, (ocr_results or {}).get(asset_id))
            if rendered_ocr is not None:
                lines.append(rendered_ocr)
    for shape in slide["shapes"]:
        line = line_fn(shape, smartart_nodes)
        if line:
            lines.append(line)
            if semantic and shape["type"] == "picture":
                asset_id = shape.get("assetId") or shape["id"]
                rendered_ocr = render_ocr_result(asset_id, (ocr_results or {}).get(asset_id))
                if rendered_ocr is not None:
                    lines.append(rendered_ocr)
    if slide["notes"]:
        lines.append(f"<notes>{escape(slide['notes'])}")
    return "\n".join(lines) + "\n"


def _html_comments_block(parsed: ParsedPresentation) -> str:
    if not parsed.comments:
        return ""
    lines = ["<!-- supplemental -->"]
    lines.extend(_structural_comment_line(comment) for comment in parsed.comments)
    return "\n".join(lines) + "\n"


def _slide_open(slide: SlideBlock) -> str:
    attrs = AttributeBuilder().add("n", slide["n"]).flag("hidden", slide["hidden"])
    background = slide.get("background")
    if background:
        attrs.add("bg", background.get("color"))
        attrs.add("bgImage", background.get("assetId"))
    return f"<slide{attrs.render()}>\n"


def _structural_shape_line(shape: ShapeBlock, smartart_nodes: dict[str, SmartArtRecord]) -> str | None:
    stype = shape["type"]
    if stype == "text":
        ph_type = shape.get("placeholderType", "")
        if ph_type in _TITLE_PH_TYPES:
            return f"<title>{_structural_inline(shape)}"
        attrs = AttributeBuilder().add("ph", ph_type or None)
        return f"<p{attrs.render()}>{_structural_inline(shape)}"
    if stype == "picture":
        asset_id = shape.get("assetId") or shape["id"]
        alt = shape.get("alt")
        attrs = AttributeBuilder().add("id", asset_id).add("alt", alt)
        return f"<img{attrs.render()}>"
    if stype == "table":
        return _structural_table(shape)
    if stype == "chart":
        attrs = (
            AttributeBuilder()
            .add("id", shape.get("chartId") or shape["id"])
            .add("type", shape.get("chartType"))
            .add("series", shape.get("seriesCount"))
            .add("points", shape.get("pointCount"))
            .flag("truncated")
        )
        return f"<chart{attrs.render()}>"
    if stype == "smartart":
        smartart_id = shape.get("smartartId") or shape["id"]
        attrs = (
            AttributeBuilder()
            .add("id", smartart_id)
            .add("type", shape.get("layoutType"))
            .add("nodes", shape.get("nodeCount"))
            .add("links", shape.get("linkCount"))
            .flag("truncated")
        )
        parts = [f"<smartart{attrs.render()}>"]
        record = smartart_nodes.get(smartart_id)
        if record is not None:
            parts.append(" ".join(node["text"] for node in record["nodes"]))
        return "".join(parts)
    if stype == "media":
        asset_id = shape.get("assetId") or shape["id"]
        attrs = AttributeBuilder().add("id", asset_id).add("kind", shape.get("kind", "media"))
        return f"<media{attrs.render()}>"
    if stype == "shape":
        attrs = AttributeBuilder().add("id", shape["id"]).add("kind", shape.get("kind"))
        return f"<shape{attrs.render()}>"
    raise AssertionError(f"Unknown shape type: {shape['type']}")


def _structural_inline(shape: ShapeBlock) -> str:
    runs = shape.get("runs")
    if runs:
        parts: list[str] = []
        for run in runs:
            text = _run_text(run)
            link = run.get("link")
            if link:
                parts.append(f"<a{AttributeBuilder().add('href', link).render()}>{text}</a>")
            else:
                parts.append(text)
        return "".join(parts)
    return escape(shape["text"])


def _structural_table(shape: ShapeBlock) -> str:
    rows = shape.get("rows", [])
    cols = max((len(row) for row in rows), default=0)
    truncated = " truncated" if len(rows) > _STRUCTURAL_TABLE_ROW_LIMIT else ""
    attrs = AttributeBuilder().add("id", shape["id"]).add("rows", len(rows)).add("cols", cols).flag("truncated", bool(truncated))
    lines = [f"<table{attrs.render()}>"]
    for row_index, _row in enumerate(rows[:_STRUCTURAL_TABLE_ROW_LIMIT]):
        cells = _table_row_markup(shape, row_index=row_index)
        lines.append(f"<tr>{cells}")
    return "\n".join(lines)


def iter_semantic(parsed: ParsedPresentation) -> Iterator[str]:
    """semantic — full structure + coordinates + inline formats."""
    yield "density=semantic\n"
    smartart_nodes = {smartart["id"]: smartart for smartart in parsed.smartarts}
    for slide in parsed.slides:
        yield _html_slide_block(slide, smartart_nodes, semantic=True, ocr_results=parsed.ocr_results)
    comments = _html_comments_block(parsed)
    if comments:
        yield comments


def _semantic_shape_line(shape: ShapeBlock, smartart_nodes: dict[str, SmartArtRecord]) -> str | None:
    stype = shape["type"]
    if stype == "text":
        tag = "title" if shape.get("placeholderType", "") in _TITLE_PH_TYPES else "p"
        return f"<{tag}{_shape_attrs(shape)}>{_semantic_inline(shape)}"
    if stype == "picture":
        asset_id = shape.get("assetId") or shape["id"]
        alt = shape.get("alt")
        picture_shape_attrs = _shape_attrs(shape, include_id=False, include_ph=False)
        head = AttributeBuilder().add("id", asset_id).add("alt", alt).render()
        return f"<img{head}{picture_shape_attrs}>"
    if stype == "table":
        return _semantic_table(shape)
    if stype == "chart":
        chart_attrs = (
            AttributeBuilder()
            .add("id", shape.get("chartId") or shape["id"])
            .add("type", shape.get("chartType"))
            .add("series", shape.get("seriesCount"))
            .add("points", shape.get("pointCount"))
            .flag("truncated")
        )
        return f"<chart{chart_attrs.render()}{_shape_attrs(shape, include_id=False, include_ph=False)}>"
    if stype == "smartart":
        smartart_id = shape.get("smartartId") or shape["id"]
        smartart_attrs = (
            AttributeBuilder()
            .add("id", smartart_id)
            .add("type", shape.get("layoutType"))
            .add("nodes", shape.get("nodeCount"))
            .add("links", shape.get("linkCount"))
            .flag("truncated")
        )
        parts = [f"<smartart{smartart_attrs.render()}{_shape_attrs(shape, include_id=False, include_ph=False)}>"]
        record = smartart_nodes.get(smartart_id)
        if record is not None:
            parts.append(" ".join(node["text"] for node in record["nodes"]))
        return "".join(parts)
    if stype == "media":
        asset_id = shape.get("assetId") or shape["id"]
        media_shape_attrs = _shape_attrs(shape, include_id=False, include_ph=False)
        media_head = AttributeBuilder().add("id", asset_id).add("kind", shape.get("kind", "media"))
        return f"<media{media_head.render()}{media_shape_attrs}>"
    if stype == "shape":
        return f"<shape{AttributeBuilder().add('kind', shape.get('kind')).render()}{_shape_attrs(shape)}>"
    raise AssertionError(f"Unknown shape type: {shape['type']}")


def _shape_attrs(shape: ShapeBlock, *, include_id: bool = True, include_ph: bool = True) -> str:
    attrs = AttributeBuilder()
    if include_id:
        attrs.add("id", shape["id"])
    if include_ph:
        ph_type = shape.get("placeholderType", "")
        if ph_type:
            attrs.add("ph", ph_type)
    for key in ("x", "y", "w", "h"):
        value = shape.get(key)
        if value is not None:
            attrs.add(key, value)
    z = shape.get("z")
    if z is not None:
        attrs.add("z", z)
    name = shape.get("name")
    if name:
        attrs.add("name", name)
    return attrs.render()


def _semantic_inline(shape: ShapeBlock) -> str:
    runs = shape.get("runs")
    if runs:
        parts: list[str] = []
        for run in runs:
            text = _run_text(run)
            fmt = run.get("format") or {}
            color = fmt.get("color")
            if color:
                text = f"<color value={color}>{text}</color>"
            if fmt.get("underline"):
                text = f"<u>{text}</u>"
            if fmt.get("italic"):
                text = f"<i>{text}</i>"
            if fmt.get("bold"):
                text = f"<b>{text}</b>"
            link = run.get("link")
            if link:
                text = f"<a{AttributeBuilder().add('href', link).render()}>{text}</a>"
            parts.append(text)
        return "".join(parts)
    return escape(shape["text"])


def _semantic_table(shape: ShapeBlock) -> str:
    rows = shape.get("rows", [])
    cols = max((len(row) for row in rows), default=0)
    truncated = " truncated" if len(rows) > _STRUCTURAL_TABLE_ROW_LIMIT else ""
    attrs = _shape_attrs(shape, include_id=False, include_ph=False)
    head = AttributeBuilder().add("id", shape["id"]).add("rows", len(rows)).add("cols", cols).flag("truncated", bool(truncated))
    lines = [f"<table{head.render()}{attrs}>"]
    for row_index, _row in enumerate(rows[:_STRUCTURAL_TABLE_ROW_LIMIT]):
        cells = _table_row_markup(shape, row_index=row_index)
        lines.append(f"<tr>{cells}")
    return "\n".join(lines)


def _structural_comment_line(comment: CommentItem) -> str:
    attrs = (
        AttributeBuilder()
        .add("id", comment["id"])
        .add("author", comment.get("author") or None)
        .add("date", comment.get("date"))
        .add("parent", comment.get("parentCommentId") or comment.get("parentId"))
        .add("slide", comment.get("slideId"))
        .add("shape", comment.get("shapeId"))
    )
    return f"<comment{attrs.render()}>{escape(comment['text'])}"


def _run_text(run: Mapping[str, object]) -> str:
    text = escape(str(run.get("text", "")))
    equation = run.get("equation")
    return f"<equation>{escape(str(equation))}</equation>" if equation else text


def _table_row_markup(shape: ShapeBlock, *, row_index: int) -> str:
    rows = shape.get("rows", [])
    cells = shape.get("tableCells")
    if cells is None or row_index >= len(cells):
        row = rows[row_index] if row_index < len(rows) else []
        return "".join(f"<td>{escape(cell)}</td>" for cell in row)
    rendered: list[str] = []
    for cell in cells[row_index]:
        if cell.get("hMerge") or cell.get("vMerge"):
            continue
        attrs = AttributeBuilder().add("colspan", cell.get("colSpan")).add("rowspan", cell.get("rowSpan"))
        rendered.append(f"<td{attrs.render()}>{escape(cell.get('text', ''))}</td>")
    return "".join(rendered)
