"""Direct DTX serialization for DOCX parsed content."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import cast
from xml.etree import ElementTree as ET

from doctokens_core.ooxml.equations.results import append_math_text
from doctokens_core.output.xml import append, element, serialize
from doctokens_core.runtime.execution import checkpoint

from ..model import AncillaryItem, Block, InlineContainer, InlineObject, OcrResultRecord, ParsedDocument, Run, TableBlock
from .common.floating import floating_textboxes, is_floating_textbox, iter_flow_page_blocks
from .common.pages import iter_block_page_segments
from .common.text import merge_text_runs
from .dtx_content import _append_chart, _append_controls, _append_ocr, _append_smartart, _append_text_with_breaks
from .dtx_runs import append_run_text, revision_parent

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
    for block_page, block in iter_flow_page_blocks(parsed_document):
        checkpoint("rendering DOCX blocks")
        section = int(block.get("section", 1))
        if emit_sections and section != current_section:
            current_section = section
            container = append(parent, "section", number=section)
            current_page = None
        if block_page != current_page:
            current_page = block_page
            append(container, "page", number=block_page)
        _append_block(container, block, density, parsed_document.ocr_results)
        if block["type"] != "table" and floating_textboxes(cast(InlineContainer, block)):
            current_page = block.get("pageEnd", block_page)
    if current_page is None:
        append(parent, "page", number=1)


def _append_block(
    parent: ET.Element,
    block: Block,
    density: str,
    ocr_results: dict[str, OcrResultRecord],
) -> None:
    controls = block.get("contentControls", [])
    container = _append_controls(parent, controls, density)
    if block["type"] == "table":
        _append_table(container, block, density, ocr_results)
        return
    name = f"h{block['level']}" if block["type"] == "heading" else "p"
    attrs: dict[str, object] = {}
    if density == "semantic":
        _add_semantic_block_attrs(attrs, block)
    node = append(container, name, **attrs)
    _append_anchors(node, block)
    if floating_textboxes(cast(InlineContainer, block)):
        for index, (page, fragment) in enumerate(iter_block_page_segments(block)):
            if index:
                append(node, "page", number=page)
            _append_inline(node, cast(InlineContainer, fragment), density, ocr_results)
        _append_floating(container, cast(InlineContainer, block), density, ocr_results)
    else:
        _append_inline(node, cast(InlineContainer, block), density, ocr_results)


def _append_anchors(node: ET.Element, block: Block) -> None:
    if block["type"] == "table":
        return
    anchors = block.get("anchors", [])
    if anchors:
        node.set("anchor", anchors[0])
        for name in anchors[1:]:
            append(node, "anchor", name=name)


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
    ocr_results: dict[str, OcrResultRecord],
) -> None:
    runs = container.get("runs")
    if not runs:
        _append_text_with_breaks(parent, container["text"])
        return
    _append_runs(parent, runs, density, ocr_results)


def _append_runs(parent: ET.Element, runs: list[Run], density: str, ocr_results: dict[str, OcrResultRecord]) -> None:
    for run in merge_text_runs(runs):
        content_parent = _append_controls(parent, run.get("contentControls", []), density)
        content_parent = revision_parent(content_parent, run, density)
        append_run_text(content_parent, run, density, lambda node, base: _append_runs(node, base, density, ocr_results))
        for inline_object in run.get("objects", []):
            if is_floating_textbox(inline_object):
                append(content_parent, "textbox-ref", id=inline_object.get("id"))
            else:
                _append_inline_object(content_parent, inline_object, density, ocr_results)


def _append_floating(
    parent: ET.Element, container: InlineContainer, density: str, ocr_results: dict[str, OcrResultRecord]
) -> None:
    for run in container.get("runs", []):
        for item in run.get("objects", []):
            if is_floating_textbox(item):
                node = _append_controls(parent, run.get("contentControls", []), density)
                _append_inline_object(revision_parent(node, run, density), item, density, ocr_results)


def _append_inline_object(
    parent: ET.Element,
    inline_object: InlineObject,
    density: str,
    ocr_results: dict[str, OcrResultRecord],
) -> None:
    object_type = inline_object["type"]
    if object_type == "image":
        append(
            parent,
            "img",
            id=inline_object.get("assetId"),
            alt=inline_object.get("alt") if density == "semantic" else None,
        )
        _append_ocr(parent, inline_object.get("assetId"), ocr_results)
    elif object_type == "drawing":
        alt = inline_object.get("alt") or inline_object.get("title") or inline_object.get("name")
        append(parent, "img", alt=alt if density == "semantic" else None)
    elif object_type == "textbox":
        node = append(
            parent, "textbox", id=inline_object.get("id"), alt=inline_object.get("alt") if density == "semantic" else None
        )
        if "blocks" in inline_object:
            blocks = inline_object["blocks"]
            for block in blocks:
                _append_block(node, block, density, ocr_results)
        else:
            _append_text_with_breaks(node, inline_object.get("text", ""))
    elif object_type == "equation":
        node = append(parent, "equation", notation="latex")
        append_math_text(
            node, inline_object.get("text") or "", inline_object.get("mathRevisions", ()) if density == "semantic" else ()
        )
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


def _append_table(parent: ET.Element, block: TableBlock, density: str, ocr_results: dict[str, OcrResultRecord]) -> None:
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


def _append_cell_content(parent: ET.Element, cell: object, density: str, ocr_results: dict[str, OcrResultRecord]) -> None:
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
        if floating_textboxes(cast(InlineContainer, block)):
            _append_block(parent, block, density, ocr_results)
            continue
        current_page: int | None = None
        for page, fragment in iter_block_page_segments(block):
            if current_page is not None and page != current_page:
                append(parent, "page", number=page)
            current_page = page
            paragraph = append(parent, "p")
            _append_anchors(paragraph, fragment)
            _append_inline(paragraph, cast(InlineContainer, fragment), density, ocr_results)


def _append_table_rows(parent: ET.Element, block: TableBlock, density: str, ocr_results: dict[str, OcrResultRecord]) -> None:
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
            _append_floating(node, item, density, parsed_document.ocr_results)


__all__ = ["iter_dtx"]
