"""Main rendering iterators for the three densities + supplemental content."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape as escape_text

from ...core.models import AncillaryItem, OcrStoredResult, ParsedDocument
from ..common.ocr import render_ocr_result
from ..common.pages import iter_page_blocks
from ..inline import inline_content
from ..plain import block_text_only, inline_text_only
from .blocks import render_block

# ── semantic rendering ──


def iter_semantic(parsed_document: ParsedDocument) -> Iterator[str]:
    """Semantic output with full document meaning and formatting."""
    yield "density=semantic\n"
    ocr_results = getattr(parsed_document, "ocr_results", None) or {}
    yield from _emit_body(parsed_document, "semantic", ocr_results)
    yield from _emit_assets(parsed_document, ocr_results, include_href=True)

    supplemental = supplemental_to_output(parsed_document, "semantic")
    if supplemental:
        yield "\n"
        yield supplemental


# ── structural rendering ──


def iter_structural(parsed_document: ParsedDocument) -> Iterator[str]:
    """Structural output with block structure and object references."""
    yield "density=structural\n"
    ocr_results = getattr(parsed_document, "ocr_results", None) or {}
    yield from _emit_body(parsed_document, "structural", ocr_results)
    yield from _emit_assets(parsed_document, ocr_results, include_href=False)

    supplemental = supplemental_to_output(parsed_document, "structural")
    if supplemental:
        yield "\n"
        yield supplemental


# ── plain rendering ──


def iter_plain(parsed_document: ParsedDocument) -> Iterator[str]:
    """plain — pure text stream. Footnotes are appended to paragraph ends, endnotes to the document end."""
    yield "density=plain\n"
    ocr_results = getattr(parsed_document, "ocr_results", None) or {}
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
    comment_order: list[str] = []
    comment_map: dict[str, str] = {}
    for comment in parsed_document.comments:
        comment_text = inline_text_only(comment, ocr_results)
        comment_id = comment.get("id")
        if comment_text and comment_id is not None:
            comment_map[comment_id] = comment_text

    parts: list[str] = []
    current_section = 0
    emit_sections = any(block.get("section", 1) != 1 for block in parsed_document.blocks)
    for block in parsed_document.blocks:
        section = block.get("section", 1)
        if emit_sections and section != current_section:
            current_section = section
            parts.append(f"[Section {section}]")
        block_text = block_text_only(block, footnote_map, endnote_order, comment_order, ocr_results)
        if block_text:
            parts.append(block_text)

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

    comment_ids = list(comment_order)
    seen_comment_ids = set(comment_ids)
    comment_ids.extend(c for c in comment_map if c not in seen_comment_ids)
    if comment_ids:
        yield "\n\n[Comments]"
        for comment_id in comment_ids:
            comment_text = comment_map.get(comment_id, "")
            if comment_text:
                yield f"\n[cmt{comment_id}: {comment_text}]"


# ── supplemental content ──


def supplemental_to_output(parsed_document: ParsedDocument, density: str) -> str:
    """Render supplemental content beyond the main body.

    Headers/footers are page chrome and appear only in semantic output;
    footnotes, endnotes, and comments are content and appear in both
    structural and semantic output.
    """
    groups: list[tuple[str, str, list[AncillaryItem]]] = [
        ("footnotes", "footnote", parsed_document.footnotes),
        ("endnotes", "endnote", parsed_document.endnotes),
        ("comments", "comment", parsed_document.comments),
    ]
    if density == "semantic":
        groups[0:0] = [
            ("headers", "header", parsed_document.headers),
            ("footers", "footer", parsed_document.footers),
        ]

    if not any(items for _group_name, _tag, items in groups):
        return ""

    lines = ["<!-- supplemental -->"]
    for _group_name, tag, items in groups:
        if not items:
            continue
        for item in items:
            attrs = f"id={item['id']}"
            if item.get("loc"):
                attrs += f" loc={escape_text(item['loc'], quote=True)}"
            author = item.get("author")
            if author is not None:
                attrs += f" author={escape_text(author, quote=True)}"
            date = item.get("date")
            if date is not None:
                attrs += f" date={escape_text(date, quote=True)}"
            anchor = item.get("anchor")
            if anchor:
                attrs += f" anchor={escape_text(anchor, quote=True)}"
            parent = item.get("parentId")
            if parent:
                attrs += f" parent={escape_text(parent, quote=True)}"
            if item.get("resolved"):
                attrs += " resolved"
            content = inline_content(item, density, parsed_document.ocr_results)
            lines.append(f"<{tag} {attrs}>{content}")
    return "\n".join(lines)


def _emit_body(parsed_document: ParsedDocument, density: str, ocr_results: dict[str, OcrStoredResult]) -> Iterator[str]:
    current_page = 0
    current_section = 0
    emit_sections = any(block.get("section", 1) != 1 for block in parsed_document.blocks)
    used_anchors = _used_anchors(parsed_document)
    for block_page, block in iter_page_blocks(parsed_document):
        section = block.get("section", 1)
        if emit_sections and section != current_section:
            current_section = section
            yield f"<section n={section}>\n"
        if block_page != current_page:
            current_page = block_page
            yield f"<page={current_page}>\n"

        yield from render_block(block, density, ocr_results, used_anchors)


def _used_anchors(parsed_document: ParsedDocument) -> set[str]:
    """Keep bookmark anchors only when a parsed navigation target refers to them."""
    anchors: set[str] = set()
    for block in parsed_document.blocks:
        if block["type"] not in {"paragraph", "heading"}:
            continue
        for run in block.get("runs", []):
            link = run.get("link")
            if link and link.get("anchor"):
                anchors.add(link["anchor"])
    return anchors


def _emit_assets(
    parsed_document: ParsedDocument,
    ocr_results: dict[str, OcrStoredResult],
    *,
    include_href: bool,
) -> Iterator[str]:
    for asset in parsed_document.assets:
        attrs = f"id={asset['id']}"
        if include_href and asset.get("href"):
            attrs += f" href={escape_text(asset['href'], quote=True)}"
        yield f"<img {attrs}>\n"
        asset_id = asset["id"]
        rendered_ocr = render_ocr_result(asset_id, ocr_results.get(asset_id))
        if rendered_ocr is None:
            yield "\n"
        else:
            yield f"{rendered_ocr}\n"
