"""Inline content rendering: run merging, format wrapping, object references."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape as escape_text

from ...core.models import InlineContainer, InlineObject, OcrStoredResult, RunFormat
from ..common.controls import wrap_control
from ..common.ocr import render_ocr_result
from ..common.text import filter_format, merge_text_runs
from ..objects import chart_to_output, smartart_to_output


def inline_content(block: InlineContainer, density: str, ocr_results: dict[str, OcrStoredResult] | None = None) -> str:
    """Combine text runs, links, images, notes, and other inline content."""
    if "runs" not in block:
        return escape_text(block["text"])

    runs = merge_text_runs(block["runs"])
    if not runs:
        return escape_text(block["text"])

    output_parts: list[str] = []
    for run in runs:
        run_text = escape_text(run["text"])
        run_format = filter_format(run)
        run_text = apply_inline_format(run_text, run_format, density)

        if density == "semantic":
            if run.get("revision") == "inserted":
                run_text = f"<ins{_revision_attrs(run)}>{run_text}</ins>"
            elif run.get("revision") == "deleted":
                run_text = f"<del{_revision_attrs(run)}>{run_text}</del>"

        field = run.get("field")
        if field and field.get("kind") == "citation" and run_text:
            key = field.get("key", "")
            if key:
                run_text = f"<cite key={escape_text(key, quote=True)}>{run_text}</cite>"

        link = run.get("link")
        if link and run_text:
            href = link.get("href", "")
            anchor = link.get("anchor", "")
            attrs = f"href={escape_text(href, quote=True)}"
            if anchor:
                attrs += f" anchor={escape_text(anchor, quote=True)}"
            run_text = f"<a {attrs}>{run_text}</a>"
        content_parts: list[str] = []
        if run_text:
            content_parts.append(run_text)
        if "objects" in run:
            content_parts.extend(render_inline_object(inline_object, density, ocr_results) for inline_object in run["objects"])
        run_content = "".join(content_parts)
        controls = run.get("contentControls", [])
        if controls and run_content:
            run_content = wrap_control(run_content, controls, density)
        if run_content:
            output_parts.append(run_content)
    # A tab immediately followed by a hard line/page break has no text-layout
    # meaning for an LLM, and would otherwise create trailing output whitespace.
    return "".join(output_parts).replace("\t\n", "\n")


def _revision_attrs(run: Mapping[str, object]) -> str:
    """Render reviewer attribution only in semantic density, where review detail is useful."""
    attrs = ""
    author = run.get("revisionAuthor")
    date = run.get("revisionDate")
    if isinstance(author, str) and author:
        attrs += f" author={escape_text(author, quote=True)}"
    if isinstance(date, str) and date:
        attrs += f" date={escape_text(date, quote=True)}"
    return attrs


def apply_inline_format(text: str, run_format: RunFormat, density: str) -> str:
    """Apply inline formatting when the selected density includes formatting."""
    if density == "structural":
        return text
    if not text or not run_format:
        return text
    if run_format.get("bg"):
        text = f"<mark value={run_format['bg']}>{text}</mark>"
    if run_format.get("highlight"):
        text = f"<mark value={run_format['highlight']}>{text}</mark>"
    if run_format.get("color"):
        text = f"<color value={run_format['color']}>{text}</color>"
    if run_format.get("strike"):
        text = f"<s>{text}</s>"
    if run_format.get("underline"):
        text = f"<u>{text}</u>"
    if run_format.get("italic"):
        text = f"<i>{text}</i>"
    if run_format.get("bold"):
        text = f"<b>{text}</b>"
    if run_format.get("superscript"):
        text = f"<sup>{text}</sup>"
    if run_format.get("subscript"):
        text = f"<sub>{text}</sub>"
    if run_format.get("smallCaps"):
        text = f"<smallcaps>{text}</smallcaps>"
    return text


def render_inline_object(
    inline_object: InlineObject,
    density: str,
    ocr_results: dict[str, OcrStoredResult] | None = None,
) -> str:
    """Render non-plain-text object references inside a paragraph."""
    object_type = inline_object["type"]

    if object_type == "image":
        return render_image_object(inline_object, density, ocr_results)

    if object_type == "drawing":
        return render_drawing_object(inline_object, density)

    if object_type == "textbox":
        return render_textbox_object(inline_object, density)

    if object_type == "equation":
        if inline_object["text"]:
            return f"<equation>{escape_text(inline_object['text'])}</equation>"
        return "<equation/>"

    if object_type == "chart":
        return render_chart_object(inline_object, density)

    if object_type == "smartart":
        return render_smartart_object(inline_object, density)

    if object_type == "footnoteRef":
        return f"<footnoteref id={inline_object['id']}/>"
    if object_type == "endnoteRef":
        return f"<endnoteref id={inline_object['id']}/>"
    if object_type == "commentRef":
        return f"<commentref id={inline_object['id']}/>"

    if object_type == "fieldInstruction":
        return f"<field instruction={escape_text(inline_object['instruction'], quote=True)}/>"

    if object_type == "embedded":
        return render_embedded_object(inline_object, density)

    return f"<unsupported type={escape_text(object_type, quote=True)}/>"


def render_image_object(
    inline_object: InlineObject,
    density: str,
    ocr_results: dict[str, OcrStoredResult] | None = None,
) -> str:
    """Render an embedded image reference with optional OCR text."""
    asset_id = inline_object.get("assetId", "")
    if density == "structural":
        img_tag = "<img>"
    else:
        attrs = f"id={asset_id}"
        if inline_object.get("alt"):
            attrs += f" alt={escape_text(inline_object['alt'], quote=True)}"
        img_tag = f"<img {attrs}>"

    rendered_ocr = render_ocr_result(asset_id, (ocr_results or {}).get(asset_id))
    if rendered_ocr is None:
        return img_tag
    return f"{img_tag}\n{rendered_ocr}"


def render_drawing_object(inline_object: InlineObject, density: str) -> str:
    """Render a drawing fallback when a concrete asset is unavailable."""
    if density == "structural":
        return "<img>"
    alt = inline_object.get("alt") or inline_object.get("title") or inline_object.get("name") or ""
    return f"<img alt={escape_text(alt, quote=True)}>" if alt else "<img>"


def render_embedded_object(inline_object: InlineObject, density: str) -> str:
    """Render an embedded OLE object with type hint."""
    attrs = f"type={escape_text(inline_object.get('embeddedType', 'unknown'), quote=True)}"
    if inline_object.get("name"):
        attrs += f" name={escape_text(inline_object['name'], quote=True)}"
    return f"<embedded {attrs}>"


def render_textbox_object(inline_object: InlineObject, density: str) -> str:
    """Render DrawingML/VML textbox content."""
    if density == "structural":
        return f"<textbox>{escape_text(inline_object['text'])}</textbox>"
    alt = inline_object.get("alt") or inline_object.get("title") or ""
    attrs = f"alt={escape_text(alt, quote=True)}" if alt else ""
    return f"<textbox {attrs}>{escape_text(inline_object['text'])}</textbox>"


def render_chart_object(inline_object: InlineObject, density: str) -> str:
    """Render a chart reference. Full data via get_resource."""
    return chart_to_output(inline_object)


def render_smartart_object(inline_object: InlineObject, density: str) -> str:
    """Render a SmartArt reference. Full structure via get_resource."""
    return smartart_to_output(inline_object)
