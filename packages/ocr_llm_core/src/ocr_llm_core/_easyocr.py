"""EasyOCR adapter (extras: [easyocr])."""

from __future__ import annotations

from typing import Any

from ._provider import OcrProvider


class EasyOcrProvider(OcrProvider):
    """OCR via EasyOCR (PyTorch-based, 80+ languages).

    Requires ``pip install ocr_llm_core[easyocr]``.
    """

    def __init__(
        self,
        lang_list: list[str],
        gpu: bool = True,
    ) -> None:
        self.lang_list = lang_list
        self.gpu = gpu
        self._reader: Any | None = None

    def extract(self, image_bytes: bytes) -> str:
        try:
            import easyocr  # type: ignore[import-not-found]
        except ImportError:
            return ""
        try:
            if self._reader is None:
                self._reader = easyocr.Reader(self.lang_list, gpu=self.gpu, verbose=False)
            texts: list[str] = self._reader.readtext(image_bytes, detail=0)
            return "\n".join(texts)
        except Exception:
            return ""
