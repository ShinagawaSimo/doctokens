"""PPTX OCR result rendering helpers."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape

from .markup import AttributeBuilder


def render_ocr_result(asset_id: str, value: object) -> str | None:
    """Render a semantic OCR sibling without leaking provider diagnostics."""
    if value is None:
        return None
    status: object
    if isinstance(value, str):
        text = value
        status = "success" if text else "error"
    elif isinstance(value, Mapping):
        raw_text = value.get("text")
        text = raw_text if isinstance(raw_text, str) else ""
        status = value.get("status")
    else:
        text = ""
        status = "error"
    attrs = AttributeBuilder().add("id", asset_id)
    if status == "success" and text:
        return f"<ocr-text{attrs.render()}>{escape(text)}"
    if status == "empty":
        return f"<ocr-text{attrs.flag('empty').render()}>"
    return f"<ocr-text{attrs.flag('error').render()}>"


__all__ = ["render_ocr_result"]
