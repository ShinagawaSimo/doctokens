"""三密度主渲染迭代器 + 补充内容。"""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from ..core.models import AncillaryItem, ParsedDocument
from ._blocks import render_block
from .inline import inline_content
from .l0 import block_text_only, inline_text_only

# ── L2 渲染 ──


def iter_l2(parsed: ParsedDocument) -> Iterator[str]:
    """L2 — 完整语义 HTML5。"""
    current_page = 0
    for block in parsed.blocks:
        block_page = block.get("page", 1)
        if block_page != current_page:
            current_page = block_page
            yield f"<page n={current_page}>\n"
        yield from render_block(block, "L2")

    yield "\n"
    for asset in parsed.assets:
        attrs = []
        attrs.append(f"id={asset['id']}")
        if asset.get("file"):
            attrs.append(f"f={escape(asset['file'], quote=True)}")
        if asset.get("href"):
            attrs.append(f"h={escape(asset['href'], quote=True)}")
        if asset.get("contentType"):
            attrs.append(f"m={escape(asset['contentType'], quote=True)}")
        yield f"<img {' '.join(attrs)}>\n"

    supplemental = supplemental_to_html5(parsed, "L2")
    if supplemental:
        yield "\n"
        yield supplemental


# ── L1 渲染 ──


def iter_l1(parsed: ParsedDocument) -> Iterator[str]:
    """L1 — 块级结构 + 语义对象，去掉 inline 格式。"""
    current_page = 0
    for block in parsed.blocks:
        block_page = block.get("page", 1)
        if block_page != current_page:
            current_page = block_page
            yield f"<page n={current_page}>\n"
        yield from render_block(block, "L1")

    yield "\n"
    for asset in parsed.assets:
        attrs = f"id={asset['id']}"
        if asset.get("file"):
            attrs += f" f={escape(asset['file'], quote=True)}"
        yield f"<img {attrs}>\n"

    supplemental = supplemental_to_html5(parsed, "L1")
    if supplemental:
        yield "\n"
        yield supplemental


# ── L0 渲染 ──


def iter_l0(parsed: ParsedDocument) -> Iterator[str]:
    """L0 — 纯文本流。脚注拼段末，尾注拼文末。"""
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
    """L1/L2：输出正文之外的补充文本。"""
    groups: list[tuple[str, str, list[AncillaryItem]]] = [
        ("headers", "hdr", parsed.headers),
        ("footers", "ftr", parsed.footers),
        ("footnotes", "fn", parsed.footnotes),
        ("endnotes", "en", parsed.endnotes),
        ("comments", "cm", parsed.comments),
    ]
    if density == "L1":
        groups = [
            ("footnotes", "fn", parsed.footnotes),
            ("endnotes", "en", parsed.endnotes),
            ("comments", "cm", parsed.comments),
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
                attrs += f" a={escape(author, quote=True)}"
            date = item.get("date")
            if date is not None:
                attrs += f" d={escape(date, quote=True)}"
            content = inline_content(item, density)
            lines.append(f"<{tag} {attrs}>{content}")
    return "\n".join(lines)
