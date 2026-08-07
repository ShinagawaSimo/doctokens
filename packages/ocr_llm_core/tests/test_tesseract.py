"""Contract tests for TesseractProvider."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

from ocr_llm_core._tesseract import TesseractProvider


class TesseractProviderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Register mock optional dependencies so patch() can resolve them.
        if "pytesseract" not in sys.modules:
            sys.modules["pytesseract"] = MagicMock()
        if "PIL" not in sys.modules:
            sys.modules["PIL"] = MagicMock()
        if "PIL.Image" not in sys.modules:
            sys.modules["PIL.Image"] = MagicMock()

    def test_implements_ocr_provider(self) -> None:
        from ocr_llm_core._provider import OcrProvider

        self.assertIsInstance(TesseractProvider(), OcrProvider)

    def test_defaults(self) -> None:
        p = TesseractProvider()
        self.assertEqual(p.lang, "eng")
        self.assertIsNone(p.tesseract_cmd)

    def test_extract_calls_image_to_string(self) -> None:
        p = TesseractProvider(lang="eng+chi_sim")
        with patch("pytesseract.image_to_string", return_value="hello world"):
            result = p.extract(b"fake-image-bytes")
        self.assertEqual(result, "hello world")

    def test_extract_returns_empty_on_error(self) -> None:
        p = TesseractProvider()
        with patch(
            "pytesseract.image_to_string",
            side_effect=RuntimeError("tesseract not found"),
        ):
            result = p.extract(b"fake")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
