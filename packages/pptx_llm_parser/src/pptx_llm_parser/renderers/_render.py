"""Main rendering iterators for the three densities."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from ..core.models import CommentItem, ParsedPresentation, ShapeBlock, SlideBlock, SmartArtRecord

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


def _html_slide_block(slide: SlideBlock, smartart_nodes: dict[str, SmartArtRecord], *, semantic: bool) -> str:
    line_fn = _semantic_shape_line if semantic else _structural_shape_line
    lines = [_slide_open(slide).rstrip("\n")]
    for shape in slide["shapes"]:
        line = line_fn(shape, smartart_nodes)
        if line:
            lines.append(line)
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
    hidden = " hidden" if slide["hidden"] else ""
    return f"<slide n={slide['n']}{hidden}>\n"


def _structural_shape_line(shape: ShapeBlock, smartart_nodes: dict[str, SmartArtRecord]) -> str | None:
    stype = shape["type"]
    if stype == "text":
        ph_type = shape.get("placeholderType", "")
        if ph_type in _TITLE_PH_TYPES:
            return f"<title>{_structural_inline(shape)}"
        ph = f" ph={ph_type}" if ph_type else ""
        return f"<p{ph}>{_structural_inline(shape)}"
    if stype == "picture":
        asset_id = shape.get("assetId") or shape["id"]
        alt = shape.get("alt")
        alt_attr = f' alt="{escape(alt, quote=True)}"' if alt else ""
        return f"<img id={asset_id}{alt_attr}>"
    if stype == "table":
        return _structural_table(shape)
    if stype == "chart":
        parts = [f"<chart id={shape.get('chartId') or shape['id']}"]
        chart_type = shape.get("chartType")
        if chart_type:
            parts.append(f" type={chart_type}")
        series_count = shape.get("seriesCount")
        if series_count is not None:
            parts.append(f" series={series_count}")
        point_count = shape.get("pointCount")
        if point_count is not None:
            parts.append(f" points={point_count}")
        parts.append(" truncated>")
        return "".join(parts)
    if stype == "smartart":
        smartart_id = shape.get("smartartId") or shape["id"]
        parts = [f"<smartart id={smartart_id}"]
        layout = shape.get("layoutType")
        if layout:
            parts.append(f" type={layout}")
        node_count = shape.get("nodeCount")
        if node_count is not None:
            parts.append(f" nodes={node_count}")
        link_count = shape.get("linkCount")
        if link_count is not None:
            parts.append(f" links={link_count}")
        parts.append(" truncated>")
        record = smartart_nodes.get(smartart_id)
        if record is not None:
            parts.append(" ".join(node["text"] for node in record["nodes"]))
        return "".join(parts)
    if stype == "media":
        asset_id = shape.get("assetId") or shape["id"]
        return f"<media id={asset_id} kind={shape.get('kind', 'media')}>"
    raise AssertionError(f"Unknown shape type: {shape['type']}")


def _structural_inline(shape: ShapeBlock) -> str:
    runs = shape.get("runs")
    if runs:
        parts: list[str] = []
        for run in runs:
            text = escape(run["text"])
            link = run.get("link")
            if link:
                parts.append(f"<a href={escape(link)}>{text}</a>")
            else:
                parts.append(text)
        return "".join(parts)
    return escape(shape["text"])


def _structural_table(shape: ShapeBlock) -> str:
    rows = shape.get("rows", [])
    cols = max((len(row) for row in rows), default=0)
    truncated = " truncated" if len(rows) > _STRUCTURAL_TABLE_ROW_LIMIT else ""
    lines = [f"<table id={shape['id']} rows={len(rows)} cols={cols}{truncated}>"]
    for row in rows[:_STRUCTURAL_TABLE_ROW_LIMIT]:
        cells = "".join(f"<td>{escape(cell)}</td>" for cell in row)
        lines.append(f"<tr>{cells}")
    return "\n".join(lines)


def iter_semantic(parsed: ParsedPresentation) -> Iterator[str]:
    """semantic — full structure + coordinates + inline formats."""
    yield "density=semantic\n"
    smartart_nodes = {smartart["id"]: smartart for smartart in parsed.smartarts}
    for slide in parsed.slides:
        yield _html_slide_block(slide, smartart_nodes, semantic=True)
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
        alt_attr = f' alt="{escape(alt, quote=True)}"' if alt else ""
        attrs = _shape_attrs(shape, include_id=False, include_ph=False)
        return f"<img id={asset_id}{alt_attr}{attrs}>"
    if stype == "table":
        return _semantic_table(shape)
    if stype == "chart":
        parts = [f"<chart id={shape.get('chartId') or shape['id']}"]
        chart_type = shape.get("chartType")
        if chart_type:
            parts.append(f" type={chart_type}")
        series_count = shape.get("seriesCount")
        if series_count is not None:
            parts.append(f" series={series_count}")
        point_count = shape.get("pointCount")
        if point_count is not None:
            parts.append(f" points={point_count}")
        parts.append(" truncated")
        parts.append(_shape_attrs(shape, include_id=False, include_ph=False))
        parts.append(">")
        return "".join(parts)
    if stype == "smartart":
        smartart_id = shape.get("smartartId") or shape["id"]
        parts = [f"<smartart id={smartart_id}"]
        layout = shape.get("layoutType")
        if layout:
            parts.append(f" type={layout}")
        node_count = shape.get("nodeCount")
        if node_count is not None:
            parts.append(f" nodes={node_count}")
        link_count = shape.get("linkCount")
        if link_count is not None:
            parts.append(f" links={link_count}")
        parts.append(" truncated")
        parts.append(_shape_attrs(shape, include_id=False, include_ph=False))
        parts.append(">")
        record = smartart_nodes.get(smartart_id)
        if record is not None:
            parts.append(" ".join(node["text"] for node in record["nodes"]))
        return "".join(parts)
    if stype == "media":
        asset_id = shape.get("assetId") or shape["id"]
        attrs = _shape_attrs(shape, include_id=False, include_ph=False)
        return f"<media id={asset_id} kind={shape.get('kind', 'media')}{attrs}>"
    raise AssertionError(f"Unknown shape type: {shape['type']}")


def _shape_attrs(shape: ShapeBlock, *, include_id: bool = True, include_ph: bool = True) -> str:
    attrs = ""
    if include_id:
        attrs += f" id={shape['id']}"
    if include_ph:
        ph_type = shape.get("placeholderType", "")
        if ph_type:
            attrs += f" ph={ph_type}"
    for key in ("x", "y", "w", "h"):
        value = shape.get(key)
        if value is not None:
            attrs += f" {key}={value}"
    z = shape.get("z")
    if z is not None:
        attrs += f" z={z}"
    name = shape.get("name")
    if name:
        attrs += f' name="{escape(name, quote=True)}"'
    return attrs


def _semantic_inline(shape: ShapeBlock) -> str:
    runs = shape.get("runs")
    if runs:
        parts: list[str] = []
        for run in runs:
            text = escape(run["text"])
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
                text = f"<a href={escape(link)}>{text}</a>"
            parts.append(text)
        return "".join(parts)
    return escape(shape["text"])


def _semantic_table(shape: ShapeBlock) -> str:
    rows = shape.get("rows", [])
    cols = max((len(row) for row in rows), default=0)
    truncated = " truncated" if len(rows) > _STRUCTURAL_TABLE_ROW_LIMIT else ""
    attrs = _shape_attrs(shape, include_id=False, include_ph=False)
    lines = [f"<table id={shape['id']} rows={len(rows)} cols={cols}{truncated}{attrs}>"]
    for row in rows[:_STRUCTURAL_TABLE_ROW_LIMIT]:
        cells = "".join(f"<td>{escape(cell)}</td>" for cell in row)
        lines.append(f"<tr>{cells}")
    return "\n".join(lines)


def _structural_comment_line(comment: CommentItem) -> str:
    parts = [f"<comment id={comment['id']}"]
    author = comment.get("author")
    if author:
        parts.append(f" author={escape(author)}")
    date = comment.get("date")
    if date:
        parts.append(f" date={date}")
    parent_id = comment.get("parentId")
    if parent_id:
        parts.append(f" parent={parent_id}")
    parts.append(">")
    return "".join(parts) + escape(comment["text"])
