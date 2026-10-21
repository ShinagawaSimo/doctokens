"""Direct DTX serialization for PowerPoint parsed content."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from xml.etree import ElementTree as ET

from ooxml_llm_core.doctokens_xml import append, element, serialize, text

from ..core.models import (
    ChartRecord,
    CommentItem,
    OcrStoredResult,
    Paragraph,
    ParsedPresentation,
    Run,
    ShapeBlock,
    SlideBlock,
    SmartArtRecord,
)
from .charts import append_chart_preview
from .diagrams import append_diagram

_TABLE_ROW_LIMIT = 30
_TITLE_PLACEHOLDERS = {"title", "ctrTitle"}


def iter_dtx(presentation: ParsedPresentation, density: str) -> Iterator[str]:
    """Yield one well-formed DTX presentation directly from PPTX IR."""
    root = element("presentation", density=density, format="pptx")
    smartarts = {item["id"]: item for item in presentation.smartarts}
    charts = {item["id"]: item for item in presentation.charts}
    for slide in presentation.slides:
        _append_slide(root, slide, density, smartarts, charts, presentation.ocr_results)
    _append_comments(root, presentation.comments)
    yield serialize(root)


def _append_slide(
    parent: ET.Element,
    slide: SlideBlock,
    density: str,
    smartarts: dict[str, SmartArtRecord],
    charts: dict[str, ChartRecord],
    ocr_results: Mapping[str, OcrStoredResult],
) -> None:
    slide_attrs: dict[str, object] = {"number": slide["n"], "hidden": True if slide["hidden"] else None}
    if slide.get("section"):
        slide_attrs["section"] = slide["section"]
    if density == "semantic" and slide.get("background"):
        background = slide["background"]
        assert background is not None
        slide_attrs["background_color"] = background.get("color")
        slide_attrs["background_image"] = background.get("assetId")
    node = append(parent, "slide", **slide_attrs)
    groups = {group["id"]: group for shape in slide["shapes"] for group in shape.get("groups", [])}
    if groups:
        directory = append(node, "groups")
        for group in groups.values():
            append(directory, "group", id=group["id"], name=group.get("name"), parent=group.get("parent"))
    for reference in slide.get("commentRefs", []):
        append(node, "comment-ref", id=reference["id"], shape=reference.get("shapeId"))
    if density == "semantic" and slide.get("background"):
        background = slide["background"]
        assert background is not None
        _append_ocr(node, background.get("assetId"), ocr_results)
    for shape in slide["shapes"]:
        _append_shape(node, shape, density, smartarts, charts, ocr_results)
    if slide["notes"]:
        append(node, "speaker-notes", slide["notes"])


def _append_shape(
    parent: ET.Element,
    shape: ShapeBlock,
    density: str,
    smartarts: dict[str, SmartArtRecord],
    charts: dict[str, ChartRecord],
    ocr_results: Mapping[str, OcrStoredResult],
) -> None:
    shape_type = shape["type"]
    if shape_type == "text":
        title = shape.get("placeholderType") in _TITLE_PLACEHOLDERS
        attrs = _text_shape_attrs(shape, density)
        paragraphs = shape.get("paragraphs", [])
        if len(paragraphs) > 1:
            node = append(parent, "textbox", role="title" if title else None, **attrs)
            for paragraph in paragraphs:
                child = append(node, "p", **_paragraph_attrs(paragraph, nested=True))
                _append_runs(child, paragraph.get("runs", []), paragraph.get("text", ""), density)
        else:
            if paragraphs:
                attrs.update(_paragraph_attrs(paragraphs[0], nested=False))
            node = append(parent, "title" if title else "p", **attrs)
            _append_shape_text(node, shape, density)
        return
    if shape_type == "picture":
        attrs = _shape_attrs(shape, density)
        attrs["id"] = shape.get("assetId") or shape["id"]
        if shape.get("alt"):
            attrs["alt"] = shape["alt"]
        if shape.get("embeddedType"):
            attrs["kind"] = "ole-preview"
            attrs["progid"] = shape["embeddedType"]
        append(parent, "img", **attrs)
        if density == "semantic":
            _append_ocr(parent, shape.get("assetId") or shape["id"], ocr_results)
        if shape.get("mediaKind"):
            append(
                parent,
                "media",
                id=shape.get("mediaId"),
                kind=shape["mediaKind"],
                poster=shape.get("assetId"),
                owner_shape=shape["id"],
            )
        return
    if shape_type == "table":
        _append_table(parent, shape, density)
        return
    if shape_type == "chart":
        attrs = _shape_attrs(shape, density)
        attrs.update(
            {
                "id": shape.get("chartId") or shape["id"],
                "type": shape.get("chartType"),
                "series": shape.get("seriesCount"),
                "points": shape.get("pointCount"),
                "title": shape.get("chartTitle"),
                "truncated": True,
            }
        )
        node = append(parent, "chart", **attrs)
        if chart := charts.get(shape.get("chartId", "")):
            append_chart_preview(node, chart)
        return
    if shape_type == "smartart":
        smartart_id = shape.get("smartartId") or shape["id"]
        attrs = _shape_attrs(shape, density)
        attrs.update(
            {
                "id": smartart_id,
                "type": shape.get("layoutType"),
                "nodes": shape.get("nodeCount"),
                "links": shape.get("linkCount"),
                "truncated": True if smartart_id not in smartarts else None,
            }
        )
        node = append(parent, "smartart", **attrs)
        record = smartarts.get(smartart_id)
        if record is not None:
            append_diagram(node, record)
        return
    if shape_type == "media":
        attrs = _shape_attrs(shape, density)
        attrs.update({"id": shape.get("assetId") or shape["id"], "kind": shape.get("kind", "media")})
        append(parent, "media", **attrs)
        return
    if shape_type == "shape":
        attrs = _shape_attrs(shape, density)
        attrs.update(
            {
                "kind": shape.get("kind"),
                "alt": shape.get("alt"),
                "title": shape.get("title"),
                "from_shape": shape.get("fromShape"),
                "to_shape": shape.get("toShape"),
                "progid": shape.get("embeddedType"),
                "head_end": shape.get("headEnd"),
                "tail_end": shape.get("tailEnd"),
            }
        )
        append(parent, "shape", **attrs)
        return
    raise AssertionError(f"Unknown shape type: {shape_type}")


def _text_shape_attrs(shape: ShapeBlock, density: str) -> dict[str, object]:
    if density == "semantic":
        return _shape_attrs(shape, density)
    attrs: dict[str, object] = {"shape_id": shape["id"], "placeholder": shape.get("placeholderType") or None}
    if groups := shape.get("groups"):
        attrs["group"] = groups[-1]["id"]
    if shape.get("link"):
        attrs["link"] = shape["link"]
    return attrs


def _shape_attrs(shape: ShapeBlock, density: str) -> dict[str, object]:
    attrs: dict[str, object] = {"id": shape["id"], "shape_id": shape["id"], "link": shape.get("link")}
    if groups := shape.get("groups"):
        attrs["group"] = groups[-1]["id"]
    if density != "semantic":
        return attrs
    if shape.get("placeholderType"):
        attrs["placeholder"] = shape["placeholderType"]
    if shape.get("name"):
        attrs["name"] = shape["name"]
    return attrs


def _append_shape_text(parent: ET.Element, shape: ShapeBlock, density: str) -> None:
    _append_runs(parent, shape.get("runs", []), shape["text"], density)


def _paragraph_attrs(paragraph: Paragraph, *, nested: bool) -> dict[str, object]:
    attrs: dict[str, object] = {}
    if nested or "bullet" in paragraph or "numberType" in paragraph or paragraph.get("level"):
        attrs["level"] = paragraph.get("level", 0)
    for key, name in (
        ("bullet", "bullet"),
        ("bulletSource", "bullet_source"),
        ("bulletFont", "bullet_font"),
        ("numberType", "number_type"),
        ("startAt", "start_at"),
        ("number", "number"),
    ):
        if key in paragraph:
            attrs[name] = paragraph[key]  # type: ignore[literal-required]
    return attrs


def _append_runs(parent: ET.Element, runs: list[Run], fallback: str, density: str) -> None:
    if not runs:
        text(parent, fallback)
        return
    for run in runs:
        node = parent
        if density == "semantic":
            formatting = run.get("format") or {}
            if formatting.get("color"):
                node = append(node, "color", value=formatting["color"])
            if formatting.get("underline"):
                node = append(node, "u")
            if formatting.get("italic"):
                node = append(node, "i")
            if formatting.get("bold"):
                node = append(node, "b")
        if run.get("link"):
            node = append(node, "a", href=run["link"])
        equation = run.get("equation")
        if equation:
            append(node, "equation", str(equation), notation="latex")
        else:
            text(node, run.get("text", ""))


def _append_table(parent: ET.Element, shape: ShapeBlock, density: str) -> None:
    rows = shape.get("rows", [])
    columns = max((len(row) for row in rows), default=0)
    truncated = len(rows) > _TABLE_ROW_LIMIT
    attrs = _shape_attrs(shape, density)
    attrs.update({"id": shape["id"], "rows": len(rows), "columns": columns, "truncated": True if truncated else None})
    table = append(parent, "table", **attrs)
    for index, _row in enumerate(rows[:_TABLE_ROW_LIMIT]):
        row_node = append(table, "tr")
        _append_table_cells(row_node, shape, index)


def _append_table_cells(parent: ET.Element, shape: ShapeBlock, row_index: int) -> None:
    cells = shape.get("tableCells")
    if cells is None or row_index >= len(cells):
        for value in shape.get("rows", [])[row_index]:
            append(parent, "td", value)
        return
    for cell in cells[row_index]:
        if cell.get("hMerge") or cell.get("vMerge"):
            continue
        append(
            parent,
            "td",
            cell.get("text", ""),
            colspan=cell.get("colSpan") if cell.get("colSpan", 1) != 1 else None,
            rowspan=cell.get("rowSpan") if cell.get("rowSpan", 1) != 1 else None,
        )


def _append_comments(parent: ET.Element, comments: list[CommentItem]) -> None:
    if not comments:
        return
    group = append(parent, "comments")
    for comment in comments:
        append(
            group,
            "comment",
            comment["text"],
            id=comment["id"],
            author=comment.get("author"),
            date=comment.get("date"),
            parent=comment.get("parentCommentId") or comment.get("parentId"),
            slide=comment.get("slideId"),
            shape=comment.get("shapeId"),
        )


def _append_ocr(parent: ET.Element, asset_id: str | None, values: Mapping[str, OcrStoredResult]) -> None:
    if not asset_id or asset_id not in values:
        return
    value = values[asset_id]
    recognized = _ocr_text(value)
    if recognized:
        append(parent, "ocr-text", recognized, id=asset_id)
    elif isinstance(value, dict) and value.get("status") == "empty":
        append(parent, "ocr-text", id=asset_id, empty=True)
    else:
        append(parent, "ocr-text", id=asset_id, error=True)


def _ocr_text(value: OcrStoredResult) -> str:
    if isinstance(value, str):
        return value
    if value.get("status") == "success":
        text_value = value.get("text")
        return text_value if isinstance(text_value, str) else ""
    return ""


__all__ = ["iter_dtx"]
