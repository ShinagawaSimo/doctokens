"""Plain-text rendering helpers."""

from __future__ import annotations

from typing import cast

from doctokens_core.ooxml.charts.preview import plain_chart
from doctokens_core.output.diagram_preview import diagram_plain
from doctokens_core.output.ocr import plain_ocr
from doctokens_core.output.plain import page_marker

from ...model import Block, ContentControl, InlineContainer, InlineObject, OcrResultRecord, TableBlock, TableCell, TableRow
from ...model.traversal import iter_blocks, iter_runs
from ..common import constants as _constants
from ..common.controls import controlled_text, wrap_plain_control
from ..common.floating import floating_textboxes, is_floating_textbox
from ..common.pages import iter_block_page_segments
from ..common.text import merge_text_runs


def _string_field(value: object, default: str = "") -> str:
    """Return a string field from parser dictionaries without leaking object values."""
    return value if isinstance(value, str) else default


def block_text_only(
    block: Block,
    footnote_map: dict[str, str],
    endnote_order: list[str],
    ocr_results: dict[str, OcrResultRecord] | None = None,
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

    return text


def inline_text_only(
    block: InlineContainer,
    ocr_results: dict[str, OcrResultRecord] | None = None,
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

    parts: list[tuple[str, list[ContentControl]]] = []
    for run in runs:
        run_parts: list[str] = []
        text = run["text"]
        if ruby := run.get("ruby"):
            base = cast(InlineContainer, {"text": text, "runs": ruby["baseRuns"]})
            run_parts.append(inline_text_only(base, ocr_results, include_floating=False))
        elif text:
            run_parts.append(text)

        if "objects" in run:
            run_parts.extend(
                plain_object_placeholder(item, ocr_results) for item in run["objects"] if not is_floating_textbox(item)
            )
        run_content = "".join(run_parts)
        controls = _controls(run.get("contentControls"))
        parts.append((run_content, controls))
    content = controlled_text(parts)
    controls = _controls(block.get("contentControls"))
    content = wrap_plain_control(content, controls) if controls else content
    return _with_floating_stories(content, block, ocr_results) if include_floating else content


def _with_floating_stories(content: str, block: InlineContainer, ocr_results: dict[str, OcrResultRecord] | None) -> str:
    stories = floating_textboxes(block)
    if not stories:
        return content
    parts = [content]
    parts.extend(f"[Textbox]\n{plain_object_placeholder(item, ocr_results)}" for item in stories)
    return "\n\n".join(part for part in parts if part)


def _controls(value: object) -> list[ContentControl]:
    if not isinstance(value, list):
        return []
    return cast(list[ContentControl], value)


def plain_object_placeholder(
    inline_object: InlineObject,
    ocr_results: dict[str, OcrResultRecord] | None = None,
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
        return ""
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
    ocr_results: dict[str, OcrResultRecord] | None = None,
) -> str:
    """Render a compact plain-text image summary."""
    label = _string_field(inline_object.get("alt")) or _string_field(inline_object.get("title"))
    asset_id = _string_field(inline_object.get("assetId"))
    marker = f"[Image {label}]" if label else "[Image]"
    recognized = plain_ocr((ocr_results or {}).get(asset_id)) if asset_id else ""
    return marker + ("\n" + recognized if recognized else "")


def plain_chart_placeholder(inline_object: InlineObject) -> str:
    """Render a compact plain-text chart summary."""
    if "series" not in inline_object:
        return "[Unparsed chart]"
    return plain_chart(
        inline_object.get("id"),
        _string_field(inline_object.get("chartType"), "?"),
        _string_field(inline_object.get("title")),
        [item["name"] for item in inline_object.get("series", []) if item.get("name")],
        inline_object.get("seriesCount", len(inline_object.get("series", []))),
    )


def plain_smartart_placeholder(inline_object: InlineObject) -> str:
    """Render a compact plain-text SmartArt summary."""
    if "nodes" not in inline_object:
        return "[Unparsed SmartArt]"
    return diagram_plain(
        [node["text"] for node in inline_object["nodes"]],
        inline_object.get("id"),
        link_count=len(inline_object.get("links", [])),
    )


def collect_refs(block: InlineContainer, ref_type: str) -> list[str]:
    """Collect inline reference IDs of one type (footnoteRef/endnoteRef/commentRef)."""
    reference_ids: list[str] = []
    if "runs" not in block:
        return reference_ids
    containers: list[InlineContainer] = [block]
    containers.extend(
        child
        for run in iter_runs(block["runs"])
        for item in run.get("objects", [])
        for child in iter_blocks(item.get("blocks", []))
        if child["type"] in {"paragraph", "heading"}
    )
    return [
        ref_id
        for container in containers
        for run in iter_runs(container.get("runs", []))
        for item in run.get("objects", [])
        if item["type"] == ref_type and (ref_id := item.get("id")) is not None
    ]


def table_text_only(block: TableBlock, ocr_results: dict[str, OcrResultRecord] | None = None) -> str:
    """Render a table as tab-separated plain text, truncating very large tables."""
    rows = block["rows"]
    if len(rows) > _constants._TABLE_TRUNCATE_PLAIN:
        first_row = rows[0]
        header_line = _plain_row_text(first_row, ocr_results)
        total_rows = len(rows)
        column_count = block["columnCount"]
        return f"{header_line}\n[Table truncated: {total_rows} rows, {column_count} cols]"

    row_texts = [_plain_row_text(row, ocr_results) for row in rows]
    return "\n".join(row_texts)


def _plain_row_text(row: TableRow, ocr_results: dict[str, OcrResultRecord] | None) -> str:
    parts: list[str] = []
    for cell in row["cells"]:
        parts.extend("" for _ in range(max(0, cell["colIndex"] - len(parts))))
        parts.append(_plain_cell_text(cell, ocr_results))
        parts.extend("" for _ in range(cell["colSpan"] - 1))
    if not row["cells"]:
        parts.extend("" for _ in range(row.get("gridBefore", 0)))
    parts.extend("" for _ in range(row.get("gridAfter", 0)))
    value = "\t".join(parts)
    controls = row.get("contentControls", [])
    return wrap_plain_control(value, controls) if controls else value


def _plain_cell_text(cell: TableCell, ocr_results: dict[str, OcrResultRecord] | None) -> str:
    parts: list[str] = []
    for child in cell["blocks"]:
        if child["type"] == "table":
            parts.append(table_text_only(child, ocr_results))
        else:
            parts.append(inline_text_only(child, ocr_results))
    rendered = "\n".join(part for part in parts if part)
    controls = cell.get("contentControls", [])
    return wrap_plain_control(rendered, controls) if controls else rendered
