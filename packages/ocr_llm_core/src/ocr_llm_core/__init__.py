"""ocr_llm_core — optional OCR provider layer for LLM document parsers."""

from __future__ import annotations

from ._batch import run_ocr_batch
from ._easyocr import EasyOcrProvider
from ._paddle_vl import PaddleVLProvider
from ._provider import OcrProvider, OcrResult, OcrStatus
from ._tesseract import TesseractProvider
from ._version import __version__

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
