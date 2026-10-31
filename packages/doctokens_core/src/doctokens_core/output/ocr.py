"""OCR reading markers shared by Office renderers, without engine diagnostics."""

from collections.abc import Mapping
from xml.etree import ElementTree as ET

from ..contracts.ocr import OcrResultRecord
from .xml import append


def append_ocr(parent: ET.Element, asset_id: str | None, values: Mapping[str, OcrResultRecord]) -> None:
    result = values.get(asset_id or "")
    if result is None:
        return
    if result.get("status") == "success" and result.get("text"):
        append(parent, "ocr-text", result["text"], id=asset_id, low_confidence=True if result.get("low_confidence") else None)
    elif result.get("status") == "error":
        append(parent, "ocr-text", id=asset_id, error=True)


def plain_ocr(result: OcrResultRecord | None) -> str:
    if result is None:
        return ""
    if result.get("status") == "success" and result.get("text"):
        return ("[OCR low-confidence] " if result.get("low_confidence") else "[OCR] ") + result["text"]
    return "[OCR failed]" if result.get("status") == "error" else ""
