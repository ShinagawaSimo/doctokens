"""三密度主渲染迭代器 + 补充内容。"""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from ..core.models import AncillaryItem, ParsedDocument
from ._blocks import render_block
from .inline import inline_content
from .l0 import block_text_only, inline_text_only


def _paragraph_text(block, density: str, ocr_results: dict[str, str] | None = None) -> str:
    """Extract rendered text for a single paragraph block."""
    return inline_content(block, density, ocr_results)


# ── semantic 渲染 ──


def iter_l2(parsed: ParsedDocument) -> Iterator[str]:
    """semantic — 完整语义 HTML5。每段独立一个 <p> 标签。"""
    yield "density=semantic\n"
    ocr = getattr(parsed, "ocr_results", None) or {}
    current_page = 0
    for block in parsed.blocks:
        block_page = block.get("page", 1)
        if block_page != current_page:
            current_page = block_page
            yield f"<page={current_page}>\n"

        if block["type"] == "paragraph":
            text = _paragraph_text(block, "semantic", ocr)
            yield f"<p>{text}\n"
        else:
            yield from render_block(block, "semantic", ocr)

    for asset in parsed.assets:
        attrs = f"id={asset['id']}"
        if asset.get("href"):
            attrs += f" href={escape(asset['href'], quote=True)}"
        yield f"<img {attrs}>\n"
        aid = asset["id"]
        ocr_text = ocr.get(aid)
        if ocr_text is None:
            yield "\n"
        elif ocr_text == "":
            yield f"<ocr-text id={aid} error>\n"
        else:
            yield f"<ocr-text id={aid}>{ocr_text}\n"

    supplemental = supplemental_to_html5(parsed, "semantic")
    if supplemental:
        yield "\n"
        yield supplemental


# ── structural 渲染 ──


def iter_l1(parsed: ParsedDocument) -> Iterator[str]:
    """structural — 块级结构 + 语义对象，去掉 inline 格式。"""
    yield "density=structural\n"
    ocr = getattr(parsed, "ocr_results", None) or {}
    current_page = 0
    for block in parsed.blocks:
        block_page = block.get("page", 1)
        if block_page != current_page:
            current_page = block_page
            yield f"<page={current_page}>\n"

        if block["type"] == "paragraph":
            text = _paragraph_text(block, "structural", ocr)
            yield f"<p>{text}\n"
        else:
            yield from render_block(block, "structural", ocr)

    for asset in parsed.assets:
        attrs = f"id={asset['id']}"
        yield f"<img {attrs}>\n"
        aid = asset["id"]
        ocr_text = ocr.get(aid)
        if ocr_text is None:
            yield "\n"
        elif ocr_text == "":
            yield f"<ocr-text id={aid} error>\n"
        else:
            yield f"<ocr-text id={aid}>{ocr_text}\n"

    supplemental = supplemental_to_html5(parsed, "structural")
    if supplemental:
        yield "\n"
        yield supplemental


# ── plain 渲染 ──


def iter_l0(parsed: ParsedDocument) -> Iterator[str]:
    """plain — 纯文本流。脚注拼段末，尾注拼文末。"""
    yield "density=plain\n"
    footnote_map: dict[str, str] = {}
    for fn in parsed.footnotes:
        fn_text = inline_text_only(fn)
        if fn_text and fn["id"] is not None:
            footnote_map[fn["id"]] = fn_text

    endnote_map: dict[str, str] = {}
    for en in parsed.endnotes:
        en_text = inline_text_only(en)
        if en_text and en["id"] is not None:
            endnote_map[en["id"]] = en_text

    endnote_order: list[str] = []

    parts: list[str] = []
    for block in parsed.blocks:
        text = block_text_only(block, footnote_map, endnote_order)
        if text:
            parts.append(text)

    yield "\n\n".join(parts)

    if endnote_order:
        yield "\n\n[Endnotes]"
        for endnote_id in endnote_order:
            en_text = endnote_map.get(endnote_id, "")
            if en_text:
                yield f"\n[ed{endnote_id}: {en_text}]"


# ── 补充内容 ──


def supplemental_to_html5(parsed: ParsedDocument, density: str) -> str:
    """structural/semantic：输出正文之外的补充文本。"""
    groups: list[tuple[str, str, list[AncillaryItem]]] = [
        ("headers", "header", parsed.headers),
        ("footers", "footer", parsed.footers),
        ("footnotes", "footnote", parsed.footnotes),
        ("endnotes", "endnote", parsed.endnotes),
        ("comments", "comment", parsed.comments),
    ]
    if density == "structural":
        groups = [
            ("footnotes", "footnote", parsed.footnotes),
            ("endnotes", "endnote", parsed.endnotes),
            ("comments", "comment", parsed.comments),
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
                attrs += f" loc={escape(item['loc'], quote=True)}"
            author = item.get("author")
            if author is not None:
                attrs += f" author={escape(author, quote=True)}"
            date = item.get("date")
            if date is not None:
                attrs += f" date={escape(date, quote=True)}"
            content = inline_content(item, density, None)
            lines.append(f"<{tag} {attrs}>{content}")
    return "\n".join(lines)
