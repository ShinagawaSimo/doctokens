"""Plain-text rendering helpers."""

from __future__ import annotations

from typing import cast

from ...core.models import Block, InlineContainer, InlineObject, OcrStoredResult, TableBlock
from .. import _constants
from .._ocr import ocr_text
from .._text_utils import merge_text_runs


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
        return table_text_only(block, ocr_results)

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
) -> str:
    """Extract plain text from a block-like object that carries inline runs."""
    if "runs" not in block:
        return _string_field(block.get("text", ""))

    runs = merge_text_runs(block["runs"])
    if not runs:
        return _string_field(block.get("text", ""))

    parts: list[str] = []
    for run in runs:
        text = run["text"]
        if text:
            parts.append(text)

        if "objects" in run:
            parts.extend(plain_object_placeholder(inline_object, ocr_results) for inline_object in run["objects"])
    return "".join(parts)


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
    for run in block["runs"]:
        if "objects" not in run:
            continue
        for inline_object in run["objects"]:
            ref_id = inline_object.get("id")
            if inline_object["type"] == ref_type and ref_id is not None:
                reference_ids.append(ref_id)
    return reference_ids


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
    if not ocr_results:
        return fallback
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
