"""Tesseract OCR adapter (extras: [tesseract])."""

from __future__ import annotations

import math
import threading
from io import BytesIO

from ._provider import OcrProvider, OcrResult


class TesseractProvider(OcrProvider):
    """OCR via Tesseract (system binary required)."""

    # pytesseract stores the executable path in a module-global setting.
    max_concurrency = 1
    supports_timeout = True
    _tesseract_lock = threading.RLock()

    def __init__(
        self,
        lang: str = "eng",
        tesseract_cmd: str | None = None,
        *,
        max_input_bytes: int = 50 * 1024 * 1024,
        max_pixels: int = 100_000_000,
    ) -> None:
        if not isinstance(lang, str) or not lang.strip():
            raise ValueError("lang must not be empty")
        if tesseract_cmd is not None and (not isinstance(tesseract_cmd, str) or not tesseract_cmd.strip()):
            raise ValueError("tesseract_cmd must be a non-empty string or None")
        if isinstance(max_input_bytes, bool) or not isinstance(max_input_bytes, int) or max_input_bytes <= 0:
            raise ValueError("max_input_bytes must be greater than zero")
        if isinstance(max_pixels, bool) or not isinstance(max_pixels, int) or max_pixels <= 0:
            raise ValueError("max_pixels must be greater than zero")
        self.lang = lang.strip()
        self.tesseract_cmd = tesseract_cmd
        self.max_input_bytes = max_input_bytes
        self.max_pixels = max_pixels

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
            import pytesseract  # type: ignore[import-not-found]
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
                image.load()
                with self._tesseract_lock:
                    previous_cmd = pytesseract.pytesseract.tesseract_cmd
                    try:
                        if self.tesseract_cmd is not None:
                            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
                        kwargs: dict[str, object] = {"lang": self.lang}
                        if timeout is not None:
                            kwargs["timeout"] = timeout
                        text: str = pytesseract.image_to_string(image, **kwargs)
                    finally:
                        pytesseract.pytesseract.tesseract_cmd = previous_cmd
            return OcrResult.from_text(text)
        except TimeoutError as exc:
            return OcrResult.error("timeout", str(exc) or "OCR timed out")
        except RuntimeError as exc:
            if "timeout" in str(exc).lower():
                return OcrResult.error("timeout", str(exc) or "OCR timed out")
            return OcrResult.error("engine_error", _error_message(exc))
        except Exception as exc:
            return OcrResult.error("engine_error", _error_message(exc))


def _error_message(error: BaseException) -> str:
    return (str(error).strip() or error.__class__.__name__)[:300]
