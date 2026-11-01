"""Plain-text DOCX rendering."""

from __future__ import annotations

from collections.abc import Iterator

from doctokens_core.output.plain import page_marker

from ...model import ParsedDocument
from ..common.floating import floating_textboxes, iter_flow_page_blocks
from ..plain import block_text_only, inline_text_only

# ── plain rendering ──


def iter_plain(parsed_document: ParsedDocument, *, first_page: int | None = None) -> Iterator[str]:
    """plain — pure text stream. Footnotes are appended to paragraph ends, endnotes to the document end."""
    ocr_results = parsed_document.ocr_results
    footnote_map: dict[str, str] = {}
    for footnote in parsed_document.footnotes:
        footnote_text = inline_text_only(footnote, ocr_results)
        if footnote_text and footnote["id"] is not None:
            footnote_map[footnote["id"]] = footnote_text

    endnote_map: dict[str, str] = {}
    for endnote in parsed_document.endnotes:
        endnote_text = inline_text_only(endnote, ocr_results)
        if endnote_text and endnote["id"] is not None:
            endnote_map[endnote["id"]] = endnote_text

    endnote_order: list[str] = []
    comment_map: dict[str, str] = {}
    for comment in parsed_document.comments:
        comment_text = inline_text_only(comment, ocr_results)
        comment_id = comment.get("id")
        if comment_id is not None:
            comment_map[comment_id] = f"[comment status={comment.get('status', 'unknown')}] {comment_text}".rstrip()

    page_segments = list(iter_flow_page_blocks(parsed_document))
    initial_page = first_page or (page_segments[0][0] if page_segments else 1)
    parts: list[str] = [page_marker(initial_page)]
    current_page = initial_page
    current_section = 0
    emit_sections = any(block.get("section", 1) != 1 for block in parsed_document.blocks)
    for block_page, block in page_segments:
        while current_page < block_page:
            current_page += 1
            parts.append(page_marker(current_page))
        section = block.get("section", 1)
        if emit_sections and section != current_section:
            current_section = section
            parts.append(f"[Section {section}]")
        block_text = block_text_only(block, footnote_map, endnote_order, ocr_results)
        if block_text:
            parts.append(block_text)
        if block["type"] != "table" and floating_textboxes(block):
            current_page = block.get("pageEnd", block_page)

    for block in parsed_document.blocks:
        page_end = int(block.get("pageEnd", block.get("page", 1)))
        while current_page < page_end:
            current_page += 1
            parts.append(page_marker(current_page))

    yield "\n\n".join(parts)

    # Headers/footers repeat per section and are structural chrome: plain
    # density keeps them out. Comments are retained below — review context
    # matters to LLM consumers even at the cheapest density.

    if endnote_order:
        yield "\n\n[Endnotes]"
        for endnote_id in endnote_order:
            endnote_text = endnote_map.get(endnote_id, "")
            if endnote_text:
                yield f"\n[ed{endnote_id}: {endnote_text}]"

    if comment_map:
        yield "\n\n[Comments]"
        for comment_text in comment_map.values():
            yield f"\n{comment_text}"
