"""EasyOCR adapter (extras: [easyocr])."""

from __future__ import annotations

import math
import threading
from io import BytesIO
from typing import Any

from ._provider import OcrProvider, OcrResult


class EasyOcrProvider(OcrProvider):
    """OCR via EasyOCR (PyTorch-based, 80+ languages).

    Reader construction and inference are serialized because EasyOCR/PyTorch
    readers are not a documented thread-safe resource.  The shared OCR batcher
    uses this limit automatically.
    """

    max_concurrency = 1

    def __init__(
        self,
        lang_list: list[str],
        gpu: bool = True,
        *,
        max_input_bytes: int = 50 * 1024 * 1024,
        max_pixels: int = 100_000_000,
    ) -> None:
        if not lang_list:
            raise ValueError("lang_list must not be empty")
        if any(not isinstance(language, str) or not language.strip() for language in lang_list):
            raise ValueError("lang_list entries must be non-empty strings")
        if not isinstance(gpu, bool):
            raise TypeError("gpu must be a boolean")
        if isinstance(max_input_bytes, bool) or not isinstance(max_input_bytes, int) or max_input_bytes <= 0:
            raise ValueError("max_input_bytes must be greater than zero")
        if isinstance(max_pixels, bool) or not isinstance(max_pixels, int) or max_pixels <= 0:
            raise ValueError("max_pixels must be greater than zero")
        self.lang_list = [language.strip() for language in lang_list]
        self.gpu = gpu
        self.max_input_bytes = max_input_bytes
        self.max_pixels = max_pixels
        self._reader: Any | None = None
        self._lock = threading.RLock()

    def extract(self, image_bytes: bytes) -> str:
        return self.extract_result(image_bytes).text

    def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
        if not isinstance(image_bytes, bytes) or not image_bytes:
            return OcrResult.error("invalid_image", "image_bytes must be non-empty bytes")
        if len(image_bytes) > self.max_input_bytes:
            return OcrResult.error("input_too_large", "image exceeds max_input_bytes")
        if timeout is not None and (
            isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0
        ):
            return OcrResult.error("timeout", "OCR timeout must be greater than zero")
        try:
            import easyocr  # type: ignore[import-not-found]
            from PIL import Image  # type: ignore[import-not-found]
        except ImportError as exc:
            return OcrResult.error("dependency_missing", str(exc))
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                width, height = image.size
                if width <= 0 or height <= 0:
                    return OcrResult.error("invalid_image", "decoded image has invalid dimensions")
                if width > self.max_pixels // height:
                    return OcrResult.error("image_too_large", "decoded image exceeds max_pixels")
                image.verify()
            with self._lock:
                if self._reader is None:
                    self._reader = easyocr.Reader(self.lang_list, gpu=self.gpu, verbose=False)
                texts: object = self._reader.readtext(image_bytes, detail=0)
            if not isinstance(texts, (list, tuple)) or any(not isinstance(text, str) for text in texts):
                return OcrResult.error("invalid_result", "EasyOCR returned an unexpected result shape")
            return OcrResult.from_text("\n".join(texts))
        except TimeoutError as exc:
            return OcrResult.error("timeout", str(exc) or "OCR timed out")
        except Exception as exc:
            return OcrResult.error("engine_error", _error_message(exc))


def _error_message(error: BaseException) -> str:
    return (str(error).strip() or error.__class__.__name__)[:300]
