"""ocr_llm_core — optional OCR provider layer for LLM document parsers."""

from __future__ import annotations

from ._easyocr import EasyOcrProvider
from ._paddle_vl import PaddleVLProvider
from ._provider import OcrProvider
from ._tesseract import TesseractProvider
from ._version import __version__

__all__ = [
    "__version__",
    "EasyOcrProvider",
    "OcrProvider",
    "PaddleVLProvider",
    "TesseractProvider",
]
