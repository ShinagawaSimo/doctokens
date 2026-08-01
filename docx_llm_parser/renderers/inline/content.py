"""Inline 内容渲染：run 合并、格式包裹、对象引用。"""

from __future__ import annotations

from html import escape

from ...core.models import InlineContainer, InlineObject, RunFormat
from .._text_utils import filter_format, merge_text_runs
from ..objects import chart_to_html5, chart_type_attrs, smartart_to_html5


def inline_content(block: InlineContainer, density: str) -> str:
    """把 run 文本、链接、图片、脚注引用等合成为 inline HTML5。"""
    if "runs" not in block:
        return escape(block["text"])

    runs = merge_text_runs(block["runs"])
    if not runs:
        return escape(block["text"])

    parts: list[str] = []
    for run in runs:
        text = escape(run["text"])
        fmt = filter_format(run)
        text = apply_inline_format(text, fmt, density)

        if density == "L2":
            if run.get("revision") == "inserted":
                text = f"<ins>{text}</ins>"
            elif run.get("revision") == "deleted":
                text = f"<del>{text}</del>"

        link = run.get("link")
        if link and text:
            href = link.get("href", "")
            anchor = link.get("anchor", "")
            attrs = f"h={escape(href, quote=True)}"
            if anchor:
                attrs += f" a={escape(anchor, quote=True)}"
            text = f"<a {attrs}>{text}</a>"
        if text:
            parts.append(text)

        if "objects" in run:
            parts.extend(inline_object(obj, density) for obj in run["objects"])
    return "".join(parts)


def apply_inline_format(text: str, fmt: RunFormat, density: str) -> str:
    """用 HTML5 inline 标签包裹格式化文本。L1 不做格式包裹。"""
    if density == "L1":
        return text
    if not text or not fmt:
        return text
    if fmt.get("bg"):
        text = f"<m v={fmt['bg']}>{text}</m>"
    if fmt.get("highlight"):
        text = f"<m v={fmt['highlight']}>{text}</m>"
    if fmt.get("color"):
        text = f"<c v={fmt['color']}>{text}</c>"
    if fmt.get("strike"):
        text = f"<s>{text}</s>"
    if fmt.get("underline"):
        text = f"<u>{text}</u>"
    if fmt.get("italic"):
        text = f"<i>{text}</i>"
    if fmt.get("bold"):
        text = f"<b>{text}</b>"
    if fmt.get("superscript"):
        text = f"<sup>{text}</sup>"
    if fmt.get("subscript"):
        text = f"<sub>{text}</sub>"
    return text


def inline_object(obj: InlineObject, density: str) -> str:
    """渲染段落内的非纯文本对象引用。"""
    obj_type = obj["type"]

    if obj_type == "image":
        return image_object(obj, density)

    if obj_type == "drawing":
        return drawing_object(obj, density)

    if obj_type == "textbox":
        return textbox_object(obj, density)

    if obj_type == "equation":
        if obj["text"]:
            return f"<eq>{escape(obj['text'])}</eq>"
        return "<eq/>"

    if obj_type == "chart":
        return chart_object(obj, density)

    if obj_type == "smartart":
        return smartart_object(obj, density)

    if obj_type == "footnoteRef":
        return f"<fnr id={obj['id']}/>"
    if obj_type == "endnoteRef":
        return f"<enr id={obj['id']}/>"
    if obj_type == "commentRef":
        return f"<cmr id={obj['id']}/>"

    if obj_type == "fieldInstruction":
        return f"<fld i={escape(obj['instruction'], quote=True)}/>"

    return f"<obj t={escape(obj_type, quote=True)}/>"


def image_object(obj: InlineObject, density: str) -> str:
    """Render an embedded image reference."""
    if density == "L1":
        return "<img>"
    attrs = f"id={obj.get('assetId', '')} f={escape(obj.get('file', ''), quote=True)}"
    if obj.get("alt"):
        attrs += f" alt={escape(obj['alt'], quote=True)}"
    return f"<img {attrs}>"


def drawing_object(obj: InlineObject, density: str) -> str:
    """Render a drawing fallback when a concrete asset is unavailable."""
    if density == "L1":
        return "<img>"
    alt = obj.get("alt") or obj.get("title") or obj.get("name") or ""
    return f"<img alt={escape(alt, quote=True)}>" if alt else "<img>"


def textbox_object(obj: InlineObject, density: str) -> str:
    """Render DrawingML/VML textbox content."""
    if density == "L1":
        return f"<tb>{escape(obj['text'])}</tb>"
    alt = obj.get("alt") or obj.get("title") or ""
    attrs = f"alt={escape(alt, quote=True)}" if alt else ""
    return f"<tb {attrs}>{escape(obj['text'])}</tb>"


def chart_object(obj: InlineObject, density: str) -> str:
    """Render a chart reference with L1/L2 density differences."""
    if density != "L1":
        return chart_to_html5(obj)
    chart_id = obj.get("id", "?")
    chart_type = obj.get("chartType", "?")
    attrs = f"id={chart_id} type={chart_type}"
    if obj.get("title"):
        attrs += f" title={escape(obj['title'], quote=True)}"
    attrs += f" series={obj.get('seriesCount', 0)}"
    type_attrs = chart_type_attrs(obj, chart_type)
    if type_attrs:
        attrs += type_attrs
    return f'<chart {attrs}>\n<!-- Use extract("chart", "{chart_id}") for full data. -->\n'


def smartart_object(obj: InlineObject, density: str) -> str:
    """Render a SmartArt reference with L1/L2 density differences."""
    if density != "L1":
        return smartart_to_html5(obj)
    smartart_id = obj.get("id", "?")
    smartart_type = obj.get("layoutType", "")
    node_count = obj.get("nodeCount", 0)
    link_count = obj.get("linkCount", 0)
    node_text = " ".join(n.get("text", "") for n in (obj.get("nodes") or []))
    attrs = f"id={smartart_id} type={smartart_type} nodes={node_count} links={link_count}"
    return (
        f"<sa {attrs}>{escape(node_text)}\n"
        f'<!-- Use extract("smartart", "{smartart_id}") for full data. -->\n'
    )
