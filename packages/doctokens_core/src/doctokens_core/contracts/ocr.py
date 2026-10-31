"""Reading OCR outcomes; raw engine scores never enter document results."""

from typing import Literal, TypedDict


class OcrResultRecord(TypedDict, total=False):
    status: Literal["success", "empty", "error"]
    text: str
    error_code: str
    error_message: str
    low_confidence: bool
