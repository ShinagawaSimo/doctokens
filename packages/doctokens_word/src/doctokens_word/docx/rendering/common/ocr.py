"""OCR result normalization and rendering helpers."""

from __future__ import annotations

from collections.abc import Mapping


def ocr_text(value: object) -> str:
    """Return recognized text for a successful result record."""
    if isinstance(value, Mapping) and value.get("status") == "success":
        text = value.get("text")
        return text if isinstance(text, str) else ""
    return ""


__all__ = ["ocr_text"]
