"""Plain-text rendering helpers."""

from __future__ import annotations

from ...core.models import Block, InlineContainer, InlineObject, TableBlock
from .. import _constants
from .._text_utils import merge_text_runs


def _string_field(value: object, default: str = "") -> str:
    """Return a string field from parser dictionaries without leaking object values."""
    return value if isinstance(value, str) else default


def block_text_only(
    block: Block,
    footnote_map: dict[str, str],
    endnote_order: list[str],
) -> str:
    """Render a parsed block as plain text."""
    if block["type"] == "table":
        return table_text_only(block)

    text = inline_text_only(block)

    for footnote_id in collect_footnote_refs(block):
        fn_text = footnote_map.get(footnote_id, "")
        if fn_text:
            text += f" [fn{footnote_id}: {fn_text}]"

    for endnote_id in collect_endnote_refs(block):
        if endnote_id not in endnote_order:
            endnote_order.append(endnote_id)

    return text


def inline_text_only(block: InlineContainer) -> str:
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
            parts.extend(l0_object_placeholder(obj) for obj in run["objects"])
    return "".join(parts)


def l0_object_placeholder(obj: InlineObject) -> str:
    """Return the plain-text representation of one inline object."""
    obj_type = obj["type"]
    if obj_type in ("image", "drawing"):
        return "[Image]"
    if obj_type == "chart":
        return l0_chart_placeholder(obj)
    if obj_type == "smartart":
        return l0_smartart_placeholder(obj)
    if obj_type == "footnoteRef":
        return f"[fn{obj.get('id') or ''}]"
    if obj_type == "endnoteRef":
        return f"[ed{obj.get('id') or ''}]"
    if obj_type == "commentRef":
        return ""
    if obj_type == "equation":
        return _string_field(obj.get("text", ""))
    if obj_type == "textbox":
        return _string_field(obj.get("text", ""))
    if obj_type == "fieldInstruction":
        return ""
    if obj_type == "embedded":
        return ""
    return ""


def l0_chart_placeholder(obj: InlineObject) -> str:
    """Render a compact plain-text chart summary."""
    chart_id = _string_field(obj.get("id"), "?")
    chart_type = _string_field(obj.get("chartType"), "?")
    title = _string_field(obj.get("title"))
    series = obj.get("series") or []
    names = [item.get("name", "") for item in series if item.get("name")]
    names_str = ", ".join(names) if names else ""
    title_part = f" {title}" if title else ""
    names_part = f": {names_str}" if names_str else ""
    return f"[Chart{title_part} ({chart_type}, {len(series)} series{names_part})]"


def l0_smartart_placeholder(obj: InlineObject) -> str:
    """Render a compact plain-text SmartArt summary."""
    smartart_id = _string_field(obj.get("id"), "?")
    smartart_type = _string_field(obj.get("layoutType"))
    nodes = obj.get("nodes") or []
    node_text = " ".join(node.get("text", "") for node in nodes)
    node_count = obj.get("nodeCount", len(nodes))
    type_part = f'"{smartart_type}" ' if smartart_type else ""
    return f"[SmartArt {type_part}: {node_text} ({node_count} nodes)]"


def collect_footnote_refs(block: InlineContainer) -> list[str]:
    """Collect footnote reference IDs from inline object runs."""
    refs: list[str] = []
    if "runs" not in block:
        return refs
    for run in block["runs"]:
        if "objects" not in run:
            continue
        for obj in run["objects"]:
            ref_id = obj.get("id")
            if obj["type"] == "footnoteRef" and ref_id is not None:
                refs.append(ref_id)
    return refs


def collect_endnote_refs(block: InlineContainer) -> list[str]:
    """Collect endnote reference IDs from inline object runs."""
    refs: list[str] = []
    if "runs" not in block:
        return refs
    for run in block["runs"]:
        if "objects" not in run:
            continue
        for obj in run["objects"]:
            ref_id = obj.get("id")
            if obj["type"] == "endnoteRef" and ref_id is not None:
                refs.append(ref_id)
    return refs


def table_text_only(block: TableBlock) -> str:
    """Render a table as tab-separated plain text, truncating very large tables."""
    rows = block["rows"]
    if len(rows) > _constants._TABLE_TRUNCATE_PLAIN:
        first_row = rows[0]
        header_line = "\t".join(cell["text"] for cell in first_row["cells"])
        total_rows = len(rows)
        column_count = block["columnCount"]
        return (
            f"{header_line}\n[Table truncated: {total_rows} rows, {column_count} cols]"
        )

    row_texts = ["\t".join(cell["text"] for cell in row["cells"]) for row in rows]
    return "\n".join(row_texts)
