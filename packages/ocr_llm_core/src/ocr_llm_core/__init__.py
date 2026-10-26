"""ocr_llm_core — optional OCR provider layer for LLM document parsers."""

from __future__ import annotations

from ._version import __version__
from .models import OcrProvider, OcrResult, OcrStatus
from .processing.batch import run_ocr_batch
from .providers.easyocr import EasyOcrProvider
from .providers.paddle_vl import PaddleVLProvider
from .providers.tesseract import TesseractProvider

__all__ = [
    "EasyOcrProvider",
    "OcrProvider",
    "OcrResult",
    "OcrStatus",
    "PaddleVLProvider",
    "TesseractProvider",
    "__version__",
    "run_ocr_batch",
]
