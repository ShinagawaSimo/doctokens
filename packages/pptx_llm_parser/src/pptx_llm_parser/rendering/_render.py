"""Main output iterators for the three densities."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from html import escape as escape_text

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


def iter_plain(parsed_presentation: ParsedPresentation) -> Iterator[str]:
    """plain — pure text stream with slide separators."""
    yield "density=plain\n"
    for slide in parsed_presentation.slides:
        if slide["n"] > 1:
            yield "\n"
        section = slide.get("section")
        label = f" (Section: {section})" if section else ""
        yield f"=== Slide {slide['n']}{label} ===\n"
        yield _plain_slide_body(slide)
    comments = _plain_comments_block(parsed_presentation)
    if comments:
        yield comments


def _plain_slide_body(slide: SlideBlock) -> str:
    output_parts = [text for shape in slide["shapes"] if (text := _plain_shape_text(shape))]
    if slide["notes"]:
        output_parts.append(f"[Notes: {slide['notes']}]")
    return "\n\n".join(output_parts)


def _plain_comments_block(parsed_presentation: ParsedPresentation) -> str:
    if not parsed_presentation.comments:
        return ""
    output_lines = ["[Comments]"]
    output_lines.extend(f"[{comment['id']}: {comment['text']}]" for comment in parsed_presentation.comments)
    return "\n\n" + "\n".join(output_lines)


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
        description = shape.get("alt") or shape.get("title")
        if description:
            return f"[Shape: {description}]"
        if shape.get("link"):
            return "[Linked shape]"
        if shape.get("kind") == "connector":
            return "[Connector]"
        return ""
    raise AssertionError(f"Unknown shape type: {shape['type']}")


def _plain_table_text(shape: ShapeBlock) -> str:
    table_rows = shape.get("rows", [])
    column_count = max((len(row) for row in table_rows), default=0)
    if len(table_rows) > _PLAIN_TABLE_ROW_LIMIT:
        text_body = "\n".join("\t".join(row) for row in table_rows[:_PLAIN_TABLE_ROW_LIMIT])
        return f"{text_body}\n[Table truncated: {len(table_rows)} rows, {column_count} cols]"
    return "\n".join("\t".join(row) for row in table_rows)


def iter_structural(parsed_presentation: ParsedPresentation) -> Iterator[str]:
    """structural — block structure + semantic objects, no visual formats."""
    yield "density=structural\n"
    smartart_nodes = {smartart["id"]: smartart for smartart in parsed_presentation.smartarts}
    for slide in parsed_presentation.slides:
        yield _render_slide_output(slide, smartart_nodes, semantic=False)
    comments = _render_comments_output(parsed_presentation)
    if comments:
        yield comments


def _render_slide_output(
    slide: SlideBlock,
    smartart_nodes: dict[str, SmartArtRecord],
    *,
    semantic: bool,
    ocr_results: Mapping[str, OcrStoredResult] | None = None,
) -> str:
    render_shape_line = _semantic_shape_line if semantic else _structural_shape_line
    output_lines = [_slide_open(slide).rstrip("\n")]
    for reference in slide.get("commentRefs", []):
        attrs = AttributeBuilder().add("id", reference["id"]).add("shape", reference.get("shapeId"))
        output_lines.append(f"<commentref{attrs.render()}>")
    background = slide.get("background")
    if semantic and background is not None:
        asset_id = background.get("assetId")
        if asset_id:
            rendered_ocr = render_ocr_result(asset_id, (ocr_results or {}).get(asset_id))
            if rendered_ocr is not None:
                output_lines.append(rendered_ocr)
    for shape in slide["shapes"]:
        line = render_shape_line(shape, smartart_nodes)
        if line:
            output_lines.append(line)
            if semantic and shape["type"] == "picture":
                asset_id = shape.get("assetId") or shape["id"]
                rendered_ocr = render_ocr_result(asset_id, (ocr_results or {}).get(asset_id))
                if rendered_ocr is not None:
                    output_lines.append(rendered_ocr)
    if slide["notes"]:
        output_lines.append(f"<notes>{escape_text(slide['notes'])}")
    return "\n".join(output_lines) + "\n"


def _render_comments_output(parsed_presentation: ParsedPresentation) -> str:
    if not parsed_presentation.comments:
        return ""
    output_lines = ["<!-- supplemental -->"]
    output_lines.extend(_structural_comment_line(comment) for comment in parsed_presentation.comments)
    return "\n".join(output_lines) + "\n"


def _slide_open(slide: SlideBlock) -> str:
    attrs = AttributeBuilder().add("n", slide["n"]).add("section", slide.get("section")).flag("hidden", slide["hidden"])
    background = slide.get("background")
    if background:
        attrs.add("bg", background.get("color"))
        attrs.add("bgImage", background.get("assetId"))
    return f"<slide{attrs.render()}>\n"


def _structural_shape_line(shape: ShapeBlock, smartart_nodes: dict[str, SmartArtRecord]) -> str | None:
    shape_type = shape["type"]
    if shape_type == "text":
        placeholder_type = shape.get("placeholderType", "")
        if placeholder_type in _TITLE_PH_TYPES:
            attrs = AttributeBuilder().add("link", shape.get("link"))
            return f"<title{attrs.render()}>{_structural_inline(shape)}"
        attrs = AttributeBuilder().add("ph", placeholder_type or None).add("link", shape.get("link"))
        return f"<p{attrs.render()}>{_structural_inline(shape)}"
    if shape_type == "picture":
        asset_id = shape.get("assetId") or shape["id"]
        alt = shape.get("alt")
        attrs = AttributeBuilder().add("id", asset_id).add("alt", alt).add("link", shape.get("link"))
        return f"<img{attrs.render()}>"
    if shape_type == "table":
        return _structural_table(shape)
    if shape_type == "chart":
        attrs = (
            AttributeBuilder()
            .add("id", shape.get("chartId") or shape["id"])
            .add("type", shape.get("chartType"))
            .add("series", shape.get("seriesCount"))
            .add("points", shape.get("pointCount"))
            .add("link", shape.get("link"))
            .flag("truncated")
        )
        return f"<chart{attrs.render()}>"
    if shape_type == "smartart":
        smartart_id = shape.get("smartartId") or shape["id"]
        attrs = (
            AttributeBuilder()
            .add("id", smartart_id)
            .add("type", shape.get("layoutType"))
            .add("nodes", shape.get("nodeCount"))
            .add("links", shape.get("linkCount"))
            .add("link", shape.get("link"))
            .flag("truncated")
        )
        output_parts = [f"<smartart{attrs.render()}>"]
        smartart_record = smartart_nodes.get(smartart_id)
        if smartart_record is not None:
            output_parts.append(" ".join(node["text"] for node in smartart_record["nodes"]))
        return "".join(output_parts)
    if shape_type == "media":
        asset_id = shape.get("assetId") or shape["id"]
        attrs = AttributeBuilder().add("id", asset_id).add("kind", shape.get("kind", "media")).add("link", shape.get("link"))
        return f"<media{attrs.render()}>"
    if shape_type == "shape":
        attrs = (
            AttributeBuilder()
            .add("id", shape["id"])
            .add("kind", shape.get("kind"))
            .add("alt", shape.get("alt"))
            .add("title", shape.get("title"))
            .add("from", shape.get("fromShape"))
            .add("to", shape.get("toShape"))
            .add("link", shape.get("link"))
        )
        return f"<shape{attrs.render()}>"
    raise AssertionError(f"Unknown shape type: {shape['type']}")


def _structural_inline(shape: ShapeBlock) -> str:
    runs = shape.get("runs")
    if runs:
        inline_output_parts: list[str] = []
        for text_run in runs:
            run_text = _run_text(text_run)
            link = text_run.get("link")
            if link:
                inline_output_parts.append(f"<a{AttributeBuilder().add('href', link).render()}>{run_text}</a>")
            else:
                inline_output_parts.append(run_text)
        return "".join(inline_output_parts)
    return escape_text(shape["text"])


def _structural_table(shape: ShapeBlock) -> str:
    table_rows = shape.get("rows", [])
    column_count = max((len(row) for row in table_rows), default=0)
    truncated = " truncated" if len(table_rows) > _STRUCTURAL_TABLE_ROW_LIMIT else ""
    attrs = (
        AttributeBuilder()
        .add("id", shape["id"])
        .add("rows", len(table_rows))
        .add("cols", column_count)
        .add("link", shape.get("link"))
        .flag("truncated", bool(truncated))
    )
    output_lines = [f"<table{attrs.render()}>"]
    for row_index, _table_row in enumerate(table_rows[:_STRUCTURAL_TABLE_ROW_LIMIT]):
        cells = _table_row_markup(shape, row_index=row_index)
        output_lines.append(f"<tr>{cells}")
    return "\n".join(output_lines)


def iter_semantic(parsed_presentation: ParsedPresentation) -> Iterator[str]:
    """semantic — full structure + coordinates + inline formats."""
    yield "density=semantic\n"
    smartart_nodes = {smartart["id"]: smartart for smartart in parsed_presentation.smartarts}
    for slide in parsed_presentation.slides:
        yield _render_slide_output(slide, smartart_nodes, semantic=True, ocr_results=parsed_presentation.ocr_results)
    comments = _render_comments_output(parsed_presentation)
    if comments:
        yield comments


def _semantic_shape_line(shape: ShapeBlock, smartart_nodes: dict[str, SmartArtRecord]) -> str | None:
    shape_type = shape["type"]
    if shape_type == "text":
        tag = "title" if shape.get("placeholderType", "") in _TITLE_PH_TYPES else "p"
        return f"<{tag}{_shape_attrs(shape)}>{_semantic_inline(shape)}"
    if shape_type == "picture":
        asset_id = shape.get("assetId") or shape["id"]
        alt = shape.get("alt")
        picture_shape_attrs = _shape_attrs(shape, include_id=False, include_ph=False)
        head = AttributeBuilder().add("id", asset_id).add("alt", alt).render()
        return f"<img{head}{picture_shape_attrs}>"
    if shape_type == "table":
        return _semantic_table(shape)
    if shape_type == "chart":
        chart_attrs = (
            AttributeBuilder()
            .add("id", shape.get("chartId") or shape["id"])
            .add("type", shape.get("chartType"))
            .add("series", shape.get("seriesCount"))
            .add("points", shape.get("pointCount"))
            .flag("truncated")
        )
        return f"<chart{chart_attrs.render()}{_shape_attrs(shape, include_id=False, include_ph=False)}>"
    if shape_type == "smartart":
        smartart_id = shape.get("smartartId") or shape["id"]
        smartart_attrs = (
            AttributeBuilder()
            .add("id", smartart_id)
            .add("type", shape.get("layoutType"))
            .add("nodes", shape.get("nodeCount"))
            .add("links", shape.get("linkCount"))
            .flag("truncated")
        )
        output_parts = [f"<smartart{smartart_attrs.render()}{_shape_attrs(shape, include_id=False, include_ph=False)}>"]
        smartart_record = smartart_nodes.get(smartart_id)
        if smartart_record is not None:
            output_parts.append(" ".join(node["text"] for node in smartart_record["nodes"]))
        return "".join(output_parts)
    if shape_type == "media":
        asset_id = shape.get("assetId") or shape["id"]
        media_shape_attrs = _shape_attrs(shape, include_id=False, include_ph=False)
        media_head = AttributeBuilder().add("id", asset_id).add("kind", shape.get("kind", "media"))
        return f"<media{media_head.render()}{media_shape_attrs}>"
    if shape_type == "shape":
        shape_head = (
            AttributeBuilder()
            .add("kind", shape.get("kind"))
            .add("geometry", shape.get("geometryType"))
            .add("alt", shape.get("alt"))
            .add("title", shape.get("title"))
            .add("from", shape.get("fromShape"))
            .add("to", shape.get("toShape"))
        )
        return f"<shape{shape_head.render()}{_shape_attrs(shape)}>"
    raise AssertionError(f"Unknown shape type: {shape['type']}")


def _shape_attrs(shape: ShapeBlock, *, include_id: bool = True, include_ph: bool = True) -> str:
    attrs = AttributeBuilder()
    if include_id:
        attrs.add("id", shape["id"])
    if include_ph:
        placeholder_type = shape.get("placeholderType", "")
        if placeholder_type:
            attrs.add("ph", placeholder_type)
    for geometry_name in ("x", "y", "w", "h"):
        geometry_value = shape.get(geometry_name)
        if geometry_value is not None:
            attrs.add(geometry_name, geometry_value)
    stacking_order = shape.get("z")
    if stacking_order is not None:
        attrs.add("z", stacking_order)
    name = shape.get("name")
    if name:
        attrs.add("name", name)
    attrs.add("link", shape.get("link"))
    return attrs.render()


def _semantic_inline(shape: ShapeBlock) -> str:
    runs = shape.get("runs")
    if runs:
        inline_output_parts: list[str] = []
        for text_run in runs:
            run_text = _run_text(text_run)
            run_format = text_run.get("format") or {}
            color = run_format.get("color")
            if color:
                run_text = f"<color value={color}>{run_text}</color>"
            if run_format.get("underline"):
                run_text = f"<u>{run_text}</u>"
            if run_format.get("italic"):
                run_text = f"<i>{run_text}</i>"
            if run_format.get("bold"):
                run_text = f"<b>{run_text}</b>"
            link = text_run.get("link")
            if link:
                run_text = f"<a{AttributeBuilder().add('href', link).render()}>{run_text}</a>"
            inline_output_parts.append(run_text)
        return "".join(inline_output_parts)
    return escape_text(shape["text"])


def _semantic_table(shape: ShapeBlock) -> str:
    table_rows = shape.get("rows", [])
    column_count = max((len(row) for row in table_rows), default=0)
    truncated = " truncated" if len(table_rows) > _STRUCTURAL_TABLE_ROW_LIMIT else ""
    attrs = _shape_attrs(shape, include_id=False, include_ph=False)
    head = (
        AttributeBuilder()
        .add("id", shape["id"])
        .add("rows", len(table_rows))
        .add("cols", column_count)
        .flag("truncated", bool(truncated))
    )
    output_lines = [f"<table{head.render()}{attrs}>"]
    for row_index, _table_row in enumerate(table_rows[:_STRUCTURAL_TABLE_ROW_LIMIT]):
        cells = _table_row_markup(shape, row_index=row_index)
        output_lines.append(f"<tr>{cells}")
    return "\n".join(output_lines)


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
    return f"<comment{attrs.render()}>{escape_text(comment['text'])}"


def _run_text(run: Mapping[str, object]) -> str:
    escaped_text = escape_text(str(run.get("text", "")))
    equation = run.get("equation")
    return f"<equation>{escape_text(str(equation))}</equation>" if equation else escaped_text


def _table_row_markup(shape: ShapeBlock, *, row_index: int) -> str:
    table_rows = shape.get("rows", [])
    table_cells = shape.get("tableCells")
    if table_cells is None or row_index >= len(table_cells):
        row = table_rows[row_index] if row_index < len(table_rows) else []
        return "".join(f"<td>{escape_text(cell)}</td>" for cell in row)
    rendered_cells: list[str] = []
    for cell in table_cells[row_index]:
        if cell.get("hMerge") or cell.get("vMerge"):
            continue
        attrs = AttributeBuilder().add("colspan", cell.get("colSpan")).add("rowspan", cell.get("rowSpan"))
        rendered_cells.append(f"<td{attrs.render()}>{escape_text(cell.get('text', ''))}</td>")
    return "".join(rendered_cells)
