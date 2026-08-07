"""Inline 内容渲染：run 合并、格式包裹、对象引用。"""

from __future__ import annotations

from html import escape

from ...core.models import InlineContainer, InlineObject, RunFormat
from .._text_utils import filter_format, merge_text_runs
from ..objects import chart_to_html5, smartart_to_html5


def inline_content(block: InlineContainer, density: str, ocr_results: dict[str, str] | None = None) -> str:
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

        if density == "semantic":
            if run.get("revision") == "inserted":
                text = f"<ins>{text}</ins>"
            elif run.get("revision") == "deleted":
                text = f"<del>{text}</del>"

        link = run.get("link")
        if link and text:
            href = link.get("href", "")
            anchor = link.get("anchor", "")
            attrs = f"href={escape(href, quote=True)}"
            if anchor:
                attrs += f" anchor={escape(anchor, quote=True)}"
            text = f"<a {attrs}>{text}</a>"
        if text:
            parts.append(text)

        if "objects" in run:
            parts.extend(inline_object(obj, density, ocr_results) for obj in run["objects"])
    return "".join(parts)


def apply_inline_format(text: str, fmt: RunFormat, density: str) -> str:
    """用 HTML5 inline 标签包裹格式化文本。structural 不做格式包裹。"""
    if density == "structural":
        return text
    if not text or not fmt:
        return text
    if fmt.get("bg"):
        text = f"<mark value={fmt['bg']}>{text}</mark>"
    if fmt.get("highlight"):
        text = f"<mark value={fmt['highlight']}>{text}</mark>"
    if fmt.get("color"):
        text = f"<color value={fmt['color']}>{text}</color>"
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


def inline_object(obj: InlineObject, density: str, ocr_results: dict[str, str] | None = None) -> str:
    """渲染段落内的非纯文本对象引用。"""
    obj_type = obj["type"]

    if obj_type == "image":
        return image_object(obj, density, ocr_results)

    if obj_type == "drawing":
        return drawing_object(obj, density)

    if obj_type == "textbox":
        return textbox_object(obj, density)

    if obj_type == "equation":
        if obj["text"]:
            return f"<equation>{escape(obj['text'])}</equation>"
        return "<equation/>"

    if obj_type == "chart":
        return chart_object(obj, density)

    if obj_type == "smartart":
        return smartart_object(obj, density)

    if obj_type == "footnoteRef":
        return f"<footnoteref id={obj['id']}/>"
    if obj_type == "endnoteRef":
        return f"<endnoteref id={obj['id']}/>"
    if obj_type == "commentRef":
        return f"<commentref id={obj['id']}/>"

    if obj_type == "fieldInstruction":
        return f"<field instruction={escape(obj['instruction'], quote=True)}/>"

    if obj_type == "embedded":
        return embedded_object(obj, density)

    return f"<unsupported type={escape(obj_type, quote=True)}/>"


def image_object(obj: InlineObject, density: str, ocr_results: dict[str, str] | None = None) -> str:
    """Render an embedded image reference with optional OCR text."""
    asset_id = obj.get('assetId', '')
    if density == "structural":
        img_tag = "<img>"
    else:
        attrs = f"id={asset_id}"
        if obj.get("alt"):
            attrs += f" alt={escape(obj['alt'], quote=True)}"
        img_tag = f"<img {attrs}>"

    ocr_text = (ocr_results or {}).get(asset_id)
    if ocr_text is None:
        return img_tag
    if ocr_text == "":
        return f"{img_tag}\n<ocr-text id={asset_id} error>"
    return f"{img_tag}\n<ocr-text id={asset_id}>{ocr_text}"


def drawing_object(obj: InlineObject, density: str) -> str:
    """Render a drawing fallback when a concrete asset is unavailable."""
    if density == "structural":
        return "<img>"
    alt = obj.get("alt") or obj.get("title") or obj.get("name") or ""
    return f"<img alt={escape(alt, quote=True)}>" if alt else "<img>"


def embedded_object(obj: InlineObject, density: str) -> str:
    """Render an embedded OLE object with type hint."""
    attrs = f"type={escape(obj.get('embeddedType', 'unknown'), quote=True)}"
    if obj.get("name"):
        attrs += f" name={escape(obj['name'], quote=True)}"
    return f"<embedded {attrs}>"


def textbox_object(obj: InlineObject, density: str) -> str:
    """Render DrawingML/VML textbox content."""
    if density == "structural":
        return f"<textbox>{escape(obj['text'])}</textbox>"
    alt = obj.get("alt") or obj.get("title") or ""
    attrs = f"alt={escape(alt, quote=True)}" if alt else ""
    return f"<textbox {attrs}>{escape(obj['text'])}</textbox>"


def chart_object(obj: InlineObject, density: str) -> str:
    """Render a chart reference. Full data via get_resource."""
    return chart_to_html5(obj)


def smartart_object(obj: InlineObject, density: str) -> str:
    """Render a SmartArt reference. Full structure via get_resource."""
    return smartart_to_html5(obj)
