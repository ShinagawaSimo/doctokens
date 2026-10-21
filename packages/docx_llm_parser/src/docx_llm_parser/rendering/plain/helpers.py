"""Plain-text rendering helpers."""

from __future__ import annotations

from typing import cast

from ooxml_llm_core.doctokens_plain import page_marker

from ...core.models import Block, ContentControl, InlineContainer, InlineObject, OcrStoredResult, TableBlock
from ...core.traversal import iter_blocks
from ..common import constants as _constants
from ..common.controls import wrap_plain_control
from ..common.floating import floating_textboxes, is_floating_textbox
from ..common.ocr import ocr_text
from ..common.pages import iter_block_page_segments
from ..common.text import merge_text_runs


def _string_field(value: object, default: str = "") -> str:
    """Return a string field from parser dictionaries without leaking object values."""
    return value if isinstance(value, str) else default


def block_text_only(
    block: Block,
    footnote_map: dict[str, str],
    endnote_order: list[str],
    comment_order: list[str],
    ocr_results: dict[str, OcrStoredResult] | None = None,
) -> str:
    """Render a parsed block as plain text."""
    if block["type"] == "table":
        text = table_text_only(block, ocr_results)
        controls = _controls(block.get("contentControls"))
        return wrap_plain_control(text, controls) if controls else text

    if floating_textboxes(block):
        parts: list[str] = []
        previous_page = block["page"]
        for page, fragment in iter_block_page_segments(block):
            while previous_page < page:
                previous_page += 1
                parts.append("\n\n" + page_marker(previous_page) + "\n\n")
            parts.append(inline_text_only(cast(InlineContainer, fragment), ocr_results, include_floating=False))
        while previous_page < block.get("pageEnd", previous_page):
            previous_page += 1
            parts.append("\n\n" + page_marker(previous_page) + "\n\n")
        text = _with_floating_stories("".join(parts), block, ocr_results)
    else:
        text = inline_text_only(block, ocr_results)

    for footnote_id in collect_refs(block, "footnoteRef"):
        footnote_text = footnote_map.get(footnote_id, "")
        if footnote_text:
            text += f" [fn{footnote_id}: {footnote_text}]"

    for endnote_id in collect_refs(block, "endnoteRef"):
        if endnote_id not in endnote_order:
            endnote_order.append(endnote_id)

    for comment_id in collect_refs(block, "commentRef"):
        if comment_id not in comment_order:
            comment_order.append(comment_id)

    return text


def inline_text_only(
    block: InlineContainer,
    ocr_results: dict[str, OcrStoredResult] | None = None,
    *,
    include_floating: bool = True,
) -> str:
    """Extract plain text from a block-like object that carries inline runs."""
    if "runs" not in block:
        content = _string_field(block.get("text", ""))
        controls = _controls(block.get("contentControls"))
        return wrap_plain_control(content, controls) if controls else content

    runs = merge_text_runs(block["runs"])
    if not runs:
        content = _string_field(block.get("text", ""))
        controls = _controls(block.get("contentControls"))
        return wrap_plain_control(content, controls) if controls else content

    parts: list[str] = []
    for run in runs:
        run_parts: list[str] = []
        text = run["text"]
        if text:
            run_parts.append(text)

        if "objects" in run:
            run_parts.extend(
                plain_object_placeholder(item, ocr_results) for item in run["objects"] if not is_floating_textbox(item)
            )
        run_content = "".join(run_parts)
        controls = _controls(run.get("contentControls"))
        parts.append(wrap_plain_control(run_content, controls) if controls else run_content)
    content = "".join(parts)
    controls = _controls(block.get("contentControls"))
    content = wrap_plain_control(content, controls) if controls else content
    return _with_floating_stories(content, block, ocr_results) if include_floating else content


def _with_floating_stories(content: str, block: InlineContainer, ocr_results: dict[str, OcrStoredResult] | None) -> str:
    stories = floating_textboxes(block)
    if not stories:
        return content
    references = ", ".join(str(item["id"]) for item in stories)
    parts = [content, f"[Textboxes: {references}]"]
    parts.extend(f"[Textbox {item['id']}]\n{plain_object_placeholder(item, ocr_results)}" for item in stories)
    return "\n\n".join(part for part in parts if part)


def _controls(value: object) -> list[ContentControl]:
    if not isinstance(value, list):
        return []
    return cast(list[ContentControl], value)


def plain_object_placeholder(
    inline_object: InlineObject,
    ocr_results: dict[str, OcrStoredResult] | None = None,
) -> str:
    """Return the plain-text representation of one inline object."""
    object_type = inline_object["type"]
    if object_type in ("image", "drawing"):
        return plain_image_placeholder(inline_object, ocr_results)
    if object_type == "chart":
        return plain_chart_placeholder(inline_object)
    if object_type == "smartart":
        return plain_smartart_placeholder(inline_object)
    if object_type == "footnoteRef":
        return f"[fn{inline_object.get('id') or ''}]"
    if object_type == "endnoteRef":
        return f"[ed{inline_object.get('id') or ''}]"
    if object_type == "commentRef":
        return f"[cmt{inline_object.get('id') or ''}]"
    if object_type == "equation":
        return _string_field(inline_object.get("text", ""))
    if object_type == "textbox":
        if "blocks" in inline_object:
            return "\n".join(
                table_text_only(block, ocr_results) if block["type"] == "table" else inline_text_only(block, ocr_results)
                for block in inline_object["blocks"]
            )
        return _string_field(inline_object.get("text", ""))
    if object_type == "fieldInstruction":
        return ""
    if object_type == "embedded":
        return ""
    return ""


def plain_image_placeholder(
    inline_object: InlineObject,
    ocr_results: dict[str, OcrStoredResult] | None = None,
) -> str:
    """Render a compact plain-text image summary."""
    label = (
        _string_field(inline_object.get("alt"))
        or _string_field(inline_object.get("title"))
        or _string_field(inline_object.get("name"))
    )
    asset_id = _string_field(inline_object.get("assetId"))
    recognized_text = ocr_text((ocr_results or {}).get(asset_id)) if asset_id else ""
    parts: list[str] = []
    if label:
        parts.append(label)
    if recognized_text:
        parts.append(f"OCR: {_plain_excerpt(recognized_text)}")
    if not parts:
        return "[Image]"
    return f"[Image {'; '.join(parts)}]"


def plain_chart_placeholder(inline_object: InlineObject) -> str:
    """Render a compact plain-text chart summary."""
    chart_type = _string_field(inline_object.get("chartType"), "?")
    title = _string_field(inline_object.get("title"))
    series = inline_object.get("series") or []
    names = [item.get("name", "") for item in series if item.get("name")]
    names_str = ", ".join(names) if names else ""
    title_part = f" {title}" if title else ""
    names_part = f": {names_str}" if names_str else ""
    return f"[Chart{title_part} ({chart_type}, {len(series)} series{names_part})]"


def plain_smartart_placeholder(inline_object: InlineObject) -> str:
    """Render a compact plain-text SmartArt summary."""
    smartart_type = _string_field(inline_object.get("layoutType"))
    nodes = inline_object.get("nodes") or []
    node_text = " ".join(node.get("text", "") for node in nodes)
    node_count = inline_object.get("nodeCount", len(nodes))
    type_part = f'"{smartart_type}" ' if smartart_type else ""
    return f"[SmartArt {type_part}: {node_text} ({node_count} nodes)]"


def collect_refs(block: InlineContainer, ref_type: str) -> list[str]:
    """Collect inline reference IDs of one type (footnoteRef/endnoteRef/commentRef)."""
    reference_ids: list[str] = []
    if "runs" not in block:
        return reference_ids
    containers: list[InlineContainer] = [block]
    containers.extend(
        child
        for run in block["runs"]
        for item in run.get("objects", [])
        for child in iter_blocks(item.get("blocks", []))
        if child["type"] in {"paragraph", "heading"}
    )
    return [
        ref_id
        for container in containers
        for run in container.get("runs", [])
        for item in run.get("objects", [])
        if item["type"] == ref_type and (ref_id := item.get("id")) is not None
    ]


def table_text_only(block: TableBlock, ocr_results: dict[str, OcrStoredResult] | None = None) -> str:
    """Render a table as tab-separated plain text, truncating very large tables."""
    rows = block["rows"]
    if len(rows) > _constants._TABLE_TRUNCATE_PLAIN:
        first_row = rows[0]
        header_line = "\t".join(_plain_cell_text(cell, ocr_results) for cell in first_row["cells"])
        total_rows = len(rows)
        column_count = block["columnCount"]
        return f"{header_line}\n[Table truncated: {total_rows} rows, {column_count} cols]"

    row_texts = ["\t".join(_plain_cell_text(cell, ocr_results) for cell in row["cells"]) for row in rows]
    return "\n".join(row_texts)


def _plain_cell_text(cell: object, ocr_results: dict[str, OcrStoredResult] | None) -> str:
    if not isinstance(cell, dict):
        return ""
    fallback = _string_field(cell.get("text"))
    blocks = cell.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return fallback
    parts: list[str] = []
    for child in blocks:
        if not isinstance(child, dict):
            continue
        if child.get("type") == "table":
            parts.append(table_text_only(cast(TableBlock, child), ocr_results))
        else:
            parts.append(inline_text_only(cast(InlineContainer, child), ocr_results))
    rendered = "\n".join(part for part in parts if part)
    return rendered or fallback


def _plain_excerpt(text: str, limit: int = 120) -> str:
    """Return a short single-line excerpt for plain-text summaries."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."
