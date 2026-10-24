"""OCR result normalization and rendering helpers."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape as escape_text

from ...core.models import OcrStoredResult


def ocr_text(value: object) -> str:
    """Return recognized text for successful legacy or structured results."""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping) and value.get("status") == "success":
        text = value.get("text")
        return text if isinstance(text, str) else ""
    return ""


def render_ocr_result(asset_id: str, value: OcrStoredResult | None) -> str | None:
    """Render an OCR sibling tag without exposing provider diagnostics."""
    if value is None:
        return None
    text = ocr_text(value)
    if text:
        return f"<ocr-text id={escape_text(asset_id, quote=True)}>{escape_text(text)}"
    if isinstance(value, Mapping) and value.get("status") == "empty":
        return f"<ocr-text id={escape_text(asset_id, quote=True)} empty>"
    return f"<ocr-text id={escape_text(asset_id, quote=True)} error>"


__all__ = ["ocr_text", "render_ocr_result"]
