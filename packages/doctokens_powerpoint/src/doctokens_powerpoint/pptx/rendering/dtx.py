"""Direct DTX serialization for PowerPoint parsed content."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from xml.etree import ElementTree as ET

from doctokens_core.contracts.ocr import OcrResultRecord
from doctokens_core.ooxml.charts.preview import append_chart_preview
from doctokens_core.output.ocr import append_ocr
from doctokens_core.output.xml import append, element, serialize, text
from doctokens_core.runtime.execution import checkpoint
from doctokens_core.text.descriptions import first_readable

from ..model.presentation import (
    ChartRecord,
    CommentItem,
    Paragraph,
    ParsedPresentation,
    ShapeBlock,
    SlideBlock,
    SmartArtRecord,
)
from .diagrams import append_diagram
from .inline import append_runs

_TABLE_ROW_LIMIT = 30
_TITLE_PLACEHOLDERS = {"title", "ctrTitle"}
_READING_ROLES = {
    "subTitle": "subtitle",
    "sldNum": "slide-number",
    "dt": "date",
    "ftr": "footer",
    "hdr": "header",
    "sldImg": "slide-preview",
}


def iter_dtx(presentation: ParsedPresentation, density: str) -> Iterator[str]:
    """Yield one well-formed DTX presentation directly from PPTX IR."""
    root = element("presentation", density=density, format="pptx")
    smartarts = {item["id"]: item for item in presentation.smartarts}
    charts = {item["id"]: item for item in presentation.charts}
    for slide in presentation.slides:
        checkpoint("rendering PPTX slides")
        _append_slide(root, slide, density, smartarts, charts, presentation.ocr_results)
    _append_comments(root, presentation.comments, density)
    yield serialize(root)


def _append_slide(
    parent: ET.Element,
    slide: SlideBlock,
    density: str,
    smartarts: dict[str, SmartArtRecord],
    charts: dict[str, ChartRecord],
    ocr_results: Mapping[str, OcrResultRecord],
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
        append_ocr(node, background.get("assetId"), ocr_results)
    for shape in slide["shapes"]:
        checkpoint("rendering PPTX shapes")
        _append_shape(node, shape, density, smartarts, charts, ocr_results)
    if slide["notes"]:
        append(node, "speaker-notes", slide["notes"])


def _append_shape(
    parent: ET.Element,
    shape: ShapeBlock,
    density: str,
    smartarts: dict[str, SmartArtRecord],
    charts: dict[str, ChartRecord],
    ocr_results: Mapping[str, OcrResultRecord],
) -> None:
    shape_type = shape["type"]
    if shape_type == "unsupported":
        append(
            parent,
            "unsupported",
            type="shape",
            source=shape.get("sourceKind"),
            alt=first_readable(shape.get("alt"), shape.get("title")),
            **_shape_attrs(shape, density),
        )
        return
    if shape_type == "text":
        title = shape.get("placeholderType") in _TITLE_PLACEHOLDERS
        attrs = _shape_attrs(shape, density)
        paragraphs = shape.get("paragraphs", [])
        if len(paragraphs) > 1:
            if title:
                attrs["role"] = "title"
            node = append(parent, "textbox", **attrs)
            for paragraph in paragraphs:
                child = append(node, "p", **_paragraph_attrs(paragraph))
                append_runs(child, paragraph.get("runs", []), paragraph.get("text", ""), density)
        else:
            if paragraphs:
                attrs.update(_paragraph_attrs(paragraphs[0]))
            node = append(parent, "title" if title else "p", **attrs)
            append_runs(node, shape.get("runs", []), shape["text"], density)
        return
    if shape_type == "picture":
        attrs = _shape_attrs(shape, density)
        attrs["id"] = shape.get("assetId")
        if shape.get("alt"):
            attrs["alt"] = shape["alt"]
        if shape.get("embeddedType"):
            attrs["kind"] = "ole-preview"
            attrs["progid"] = shape["embeddedType"]
        node = append(parent, "img", **attrs)
        if shape.get("unparsed"):
            append(node, "unsupported", type="image")
        append_ocr(parent, shape.get("assetId") or shape["id"], ocr_results)
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
        chart = charts.get(shape.get("chartId", ""))
        attrs = _shape_attrs(shape, density)
        attrs.update(
            {
                "id": shape.get("chartId") if chart is not None else None,
                "type": shape.get("chartType"),
                "series": shape.get("seriesCount"),
                "points": shape.get("pointCount"),
                "title": shape.get("chartTitle"),
            }
        )
        node = append(parent, "chart", **attrs)
        if chart is not None:
            append_chart_preview(node, chart)
        else:
            append(node, "unsupported", type="chart")
        return
    if shape_type == "smartart":
        smartart_id = shape.get("smartartId") or shape["id"]
        record = smartarts.get(smartart_id)
        attrs = _shape_attrs(shape, density)
        attrs.update(
            {
                "id": smartart_id if record is not None else None,
                "type": shape.get("layoutType"),
                "nodes": shape.get("nodeCount"),
                "links": shape.get("linkCount"),
            }
        )
        node = append(parent, "smartart", **attrs)
        if record is not None:
            append_diagram(node, record, preview=True)
        else:
            append(node, "unsupported", type="smartart")
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


def _shape_attrs(shape: ShapeBlock, density: str) -> dict[str, object]:
    attrs: dict[str, object] = {"shape_id": shape["id"], "link": shape.get("link")}
    if groups := shape.get("groups"):
        attrs["group"] = groups[-1]["id"]
    role = _READING_ROLES.get(shape.get("placeholderType", ""))
    if role:
        attrs["role"] = role
    if density != "semantic":
        return attrs
    if shape.get("name"):
        attrs["name"] = shape["name"]
    return attrs


def _paragraph_attrs(paragraph: Paragraph) -> dict[str, object]:
    level = paragraph.get("level", 0)
    return {"level": level} if level else {}


def _append_table(parent: ET.Element, shape: ShapeBlock, density: str) -> None:
    rows = shape.get("rows", [])
    columns = max((len(row) for row in rows), default=0)
    truncated = len(rows) > _TABLE_ROW_LIMIT
    attrs = _shape_attrs(shape, density)
    attrs.update({"id": shape["id"], "rows": len(rows), "columns": columns, "truncated": True if truncated else None})
    table = append(parent, "table", **attrs)
    for index, _row in enumerate(rows[:_TABLE_ROW_LIMIT]):
        row_node = append(table, "tr")
        _append_table_cells(row_node, shape, index, density)


def _append_table_cells(parent: ET.Element, shape: ShapeBlock, row_index: int, density: str) -> None:
    cells = shape.get("tableCells")
    if cells is None or row_index >= len(cells):
        for value in shape.get("rows", [])[row_index]:
            append(parent, "td", value)
        return
    for cell in cells[row_index]:
        if cell.get("hMerge") or cell.get("vMerge"):
            continue
        node = append(
            parent,
            "td",
            colspan=cell.get("colSpan") if cell.get("colSpan", 1) != 1 else None,
            rowspan=cell.get("rowSpan") if cell.get("rowSpan", 1) != 1 else None,
        )
        paragraphs = cell.get("paragraphs", [])
        if len(paragraphs) > 1:
            for paragraph in paragraphs:
                child = append(node, "p", **_paragraph_attrs(paragraph))
                append_runs(child, paragraph.get("runs", []), paragraph.get("text", ""), density)
        elif paragraphs:
            append_runs(node, paragraphs[0].get("runs", []), cell.get("text", ""), density)
        else:
            text(node, cell.get("text", ""))


def _append_comments(parent: ET.Element, comments: list[CommentItem], density: str) -> None:
    if not comments:
        return
    group = append(parent, "comments")
    for comment in comments:
        node = append(
            group,
            "comment",
            None if comment.get("runs") or comment.get("unparsed") else comment["text"],
            id=comment["id"],
            author=comment.get("author") or None,
            date=comment.get("date") or None,
            parent=comment.get("parentCommentId"),
            slide=comment.get("slideId"),
            shape=comment.get("shapeId"),
            status=comment.get("status", "unknown"),
        )
        if comment.get("unparsed"):
            append(node, "unsupported", type="comments")
        elif comment.get("runs"):
            append_runs(node, comment["runs"], comment["text"], density)


__all__ = ["iter_dtx"]
