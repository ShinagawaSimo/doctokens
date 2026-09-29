"""Direct DTX serialization for DOCX parsed content."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.doctokens_xml import append, element, serialize

from ..core.models import (
    AncillaryItem,
    Block,
    InlineContainer,
    InlineObject,
    OcrStoredResult,
    ParsedDocument,
    Run,
    TableBlock,
)
from .common.pages import iter_block_page_segments, iter_page_blocks
from .common.text import filter_format, merge_text_runs
from .dtx_content import _append_chart, _append_controls, _append_ocr, _append_smartart, _append_text_with_breaks

_TABLE_ROW_LIMIT = 30


def iter_dtx(parsed_document: ParsedDocument, density: str) -> Iterator[str]:
    """Yield one well-formed DTX document directly from DOCX IR."""
    revision_view = parsed_document.metadata.get("revisionView")
    root = element(
        "document",
        density=density,
        format="docx",
        pagination="last-rendered-hints",
        revision_view=revision_view if isinstance(revision_view, str) else None,
    )
    body = append(root, "body")
    _append_body(body, parsed_document, density)
    _append_assets(root, parsed_document, density)
    _append_supplemental(root, parsed_document, density)
    yield serialize(root)


def _append_body(parent: ET.Element, parsed_document: ParsedDocument, density: str) -> None:
    current_page: int | None = None
    current_section: int | None = None
    container = parent
    emit_sections = any(block.get("section", 1) != 1 for block in parsed_document.blocks)
    used_anchors = _used_anchors(parsed_document)
    for block_page, block in iter_page_blocks(parsed_document):
        section = int(block.get("section", 1))
        if emit_sections and section != current_section:
            current_section = section
            container = append(parent, "section", number=section)
            current_page = None
        if block_page != current_page:
            current_page = block_page
            append(container, "page", number=block_page)
        _append_block(container, block, density, parsed_document.ocr_results, used_anchors)
    if current_page is None:
        append(parent, "page", number=1)


def _append_block(
    parent: ET.Element,
    block: Block,
    density: str,
    ocr_results: dict[str, OcrStoredResult],
    used_anchors: set[str],
) -> None:
    controls = block.get("contentControls", [])
    container = _append_controls(parent, controls, density)
    if block["type"] == "table":
        _append_table(container, block, density, ocr_results)
        return
    name = f"h{block['level']}" if block["type"] == "heading" else "p"
    attrs: dict[str, object] = {}
    anchor = next((item for item in block.get("anchors", []) if item in used_anchors), "")
    if anchor:
        attrs["anchor"] = anchor
    if density == "semantic":
        _add_semantic_block_attrs(attrs, block)
    node = append(container, name, **attrs)
    _append_inline(node, cast(InlineContainer, block), density, ocr_results)


def _add_semantic_block_attrs(attrs: dict[str, object], block: Block) -> None:
    alignment = block.get("alignment")
    if alignment in {"center", "right", "distribute"}:
        attrs["align"] = alignment
    if block.get("numbering"):
        attrs["numbering"] = True
    borders = block.get("borders", {})
    for side, border in borders.items() if isinstance(borders, dict) else ():
        value = str(border.get("style", "single"))
        if color := border.get("color"):
            value += f":{color}"
        attrs[f"border_{side}"] = value


def _append_inline(
    parent: ET.Element,
    container: InlineContainer,
    density: str,
    ocr_results: dict[str, OcrStoredResult],
) -> None:
    runs = container.get("runs")
    if not runs:
        _append_text_with_breaks(parent, container["text"])
        return
    for run in merge_text_runs(runs):
        content_parent = _append_controls(parent, run.get("contentControls", []), density)
        _append_run_text(content_parent, run, density)
        for inline_object in run.get("objects", []):
            _append_inline_object(content_parent, inline_object, density, ocr_results)


def _append_run_text(parent: ET.Element, run: Run, density: str) -> None:
    value = run["text"]
    if not value:
        return
    node = parent
    if density == "semantic":
        revision = run.get("revision")
        if revision == "inserted":
            node = append(node, "ins", author=run.get("revisionAuthor"), date=run.get("revisionDate"))
        elif revision == "deleted":
            node = append(node, "del", author=run.get("revisionAuthor"), date=run.get("revisionDate"))
    field = run.get("field")
    if density == "semantic" and field and field.get("kind") == "citation" and field.get("key"):
        node = append(node, "cite", key=field["key"])
    link = run.get("link")
    if link:
        node = append(node, "a", href=link.get("href") or None, anchor=link.get("anchor") or None)
    if density == "semantic":
        node = _append_format_wrappers(node, filter_format(run))
    _append_text_with_breaks(node, value)


def _append_format_wrappers(parent: ET.Element, run_format: dict[str, bool | str | None]) -> ET.Element:
    node = parent
    if run_format.get("bg") or run_format.get("highlight"):
        node = append(node, "mark", value=run_format.get("bg") or run_format.get("highlight"))
    if run_format.get("color"):
        node = append(node, "color", value=run_format["color"])
    if run_format.get("strike"):
        node = append(node, "s")
    if run_format.get("underline"):
        node = append(node, "u")
    if run_format.get("italic"):
        node = append(node, "i")
    if run_format.get("bold"):
        node = append(node, "b")
    if run_format.get("superscript"):
        node = append(node, "sup")
    if run_format.get("subscript"):
        node = append(node, "sub")
    if run_format.get("smallCaps"):
        node = append(node, "small-caps")
    return node


def _append_inline_object(
    parent: ET.Element,
    inline_object: InlineObject,
    density: str,
    ocr_results: dict[str, OcrStoredResult],
) -> None:
    object_type = inline_object["type"]
    if object_type == "image":
        append(
            parent,
            "img",
            id=inline_object.get("assetId") if density == "semantic" else None,
            alt=inline_object.get("alt") if density == "semantic" else None,
        )
        _append_ocr(parent, inline_object.get("assetId"), ocr_results)
    elif object_type == "drawing":
        alt = inline_object.get("alt") or inline_object.get("title") or inline_object.get("name")
        append(parent, "img", alt=alt if density == "semantic" else None)
    elif object_type == "textbox":
        node = append(parent, "textbox", alt=inline_object.get("alt") if density == "semantic" else None)
        _append_text_with_breaks(node, inline_object.get("text", ""))
    elif object_type == "equation":
        append(parent, "equation", inline_object.get("text") or "", notation="latex")
    elif object_type == "chart":
        _append_chart(parent, inline_object)
    elif object_type == "smartart":
        _append_smartart(parent, inline_object)
    elif object_type == "footnoteRef":
        append(parent, "footnote-ref", id=inline_object.get("id"))
    elif object_type == "endnoteRef":
        append(parent, "endnote-ref", id=inline_object.get("id"))
    elif object_type == "commentRef":
        append(parent, "comment-ref", id=inline_object.get("id"))
    elif object_type == "fieldInstruction":
        append(parent, "field", instruction=inline_object.get("instruction"))
    elif object_type == "embedded":
        append(parent, "embedded", type=inline_object.get("embeddedType", "unknown"), name=inline_object.get("name"))
    else:
        append(parent, "unsupported", type=object_type)


def _append_table(parent: ET.Element, block: TableBlock, density: str, ocr_results: dict[str, OcrStoredResult]) -> None:
    rows = block["rows"]
    truncated = len(rows) > _TABLE_ROW_LIMIT
    table = append(parent, "table", id=block["tableId"], truncated=True if truncated else None)
    for row in rows[:2] if truncated else rows:
        row_node = append(table, "tr", header=True if row.get("isHeader") else None)
        for cell in row["cells"]:
            cell_node = append(
                row_node,
                "th" if row.get("isHeader") else "td",
                colspan=cell["colSpan"] if cell["colSpan"] != 1 else None,
                rowspan=cell["rowSpan"] if cell["rowSpan"] != 1 else None,
                v_merge=cell.get("vMerge"),
            )
            _append_cell_content(cell_node, cell, density, ocr_results)


def _append_cell_content(parent: ET.Element, cell: object, density: str, ocr_results: dict[str, OcrStoredResult]) -> None:
    typed_cell = cast(dict[str, object], cell)
    blocks = typed_cell.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        _append_text_with_breaks(parent, str(typed_cell.get("text", "")))
        return
    for child in blocks:
        block = cast(Block, child)
        if block["type"] == "table":
            nested = append(
                parent,
                "nested-table",
                id=block.get("tableId"),
                rows=len(block["rows"]),
                columns=block["columnCount"],
            )
            _append_table_rows(nested, block, density, ocr_results)
            continue
        current_page: int | None = None
        for page, fragment in iter_block_page_segments(block):
            if current_page is not None and page != current_page:
                append(parent, "page", number=page)
            current_page = page
            paragraph = append(parent, "p")
            _append_inline(paragraph, cast(InlineContainer, fragment), density, ocr_results)


def _append_table_rows(parent: ET.Element, block: TableBlock, density: str, ocr_results: dict[str, OcrStoredResult]) -> None:
    for row in block["rows"]:
        row_node = append(parent, "tr", header=True if row.get("isHeader") else None)
        for cell in row["cells"]:
            cell_node = append(
                row_node,
                "th" if row.get("isHeader") else "td",
                colspan=cell["colSpan"] if cell["colSpan"] != 1 else None,
                rowspan=cell["rowSpan"] if cell["rowSpan"] != 1 else None,
                v_merge=cell.get("vMerge"),
            )
            _append_cell_content(cell_node, cell, density, ocr_results)


def _append_assets(parent: ET.Element, parsed_document: ParsedDocument, density: str) -> None:
    if not parsed_document.assets:
        return
    assets = append(parent, "assets")
    for asset in parsed_document.assets:
        append(assets, "img", id=asset["id"], href=asset.get("href") if density == "semantic" else None)
        _append_ocr(assets, asset["id"], parsed_document.ocr_results)


def _append_supplemental(parent: ET.Element, parsed_document: ParsedDocument, density: str) -> None:
    groups: list[tuple[str, Sequence[AncillaryItem]]] = [
        ("footnotes", parsed_document.footnotes),
        ("endnotes", parsed_document.endnotes),
        ("comments", parsed_document.comments),
    ]
    if density == "semantic":
        groups = [("headers", parsed_document.headers), ("footers", parsed_document.footers), *groups]
    if not any(items for _name, items in groups):
        return
    supplemental = append(parent, "supplemental")
    for group_name, items in groups:
        if not items:
            continue
        group = append(supplemental, group_name)
        singular = group_name[:-1]
        for item in items:
            node = append(
                group,
                singular,
                id=item.get("id"),
                locator=item.get("loc"),
                author=item.get("author"),
                date=item.get("date"),
                anchor=item.get("anchor"),
                parent=item.get("parentId"),
                resolved=True if item.get("resolved") else None,
            )
            _append_inline(node, item, density, parsed_document.ocr_results)


def _used_anchors(parsed_document: ParsedDocument) -> set[str]:
    anchors: set[str] = set()
    for block in parsed_document.blocks:
        if block["type"] not in {"paragraph", "heading"}:
            continue
        for run in block.get("runs", []):
            if (link := run.get("link")) and (anchor := link.get("anchor")):
                anchors.add(anchor)
    return anchors


__all__ = ["iter_dtx"]
