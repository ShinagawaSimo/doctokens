"""Tesseract OCR adapter (extras: [tesseract])."""

from __future__ import annotations

from io import BytesIO

from ._provider import OcrProvider


class TesseractProvider(OcrProvider):
    """OCR via Tesseract (system binary required).

    Requires ``pip install ocr_llm_core[tesseract]``.
    """

    def __init__(
        self,
        lang: str = "eng",
        tesseract_cmd: str | None = None,
    ) -> None:
        self.lang = lang
        self.tesseract_cmd = tesseract_cmd

    def extract(self, image_bytes: bytes) -> str:
        try:
            import pytesseract  # type: ignore[import-not-found]
        except ImportError:
            return ""
        try:
            if self.tesseract_cmd is not None:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            from PIL import Image  # type: ignore[import-not-found]

            image = Image.open(BytesIO(image_bytes))
            text: str = pytesseract.image_to_string(image, lang=self.lang)
            return text.strip()
        except Exception:
            return ""
