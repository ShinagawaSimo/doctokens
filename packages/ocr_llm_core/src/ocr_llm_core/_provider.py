"""OcrProvider abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod


class OcrProvider(ABC):
    """Minimal interface for OCR engines.

    Implementations receive raw image bytes and return extracted text
    (markdown or plain text).  The empty string signals failure or no
    text found — the caller decides whether to emit an error marker.
    """

    @abstractmethod
    def extract(self, image_bytes: bytes) -> str:
        """Extract text from *image_bytes* (JPEG, PNG, etc.).

        Returns:
            Markdown or plain-text string on success.
            ``""`` when OCR fails, times out, or finds no text.
        """
        ...
