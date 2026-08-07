"""Contract tests for EasyOcrProvider."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

from ocr_llm_core._easyocr import EasyOcrProvider


class EasyOcrProviderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Register mock optional dependency so patch() can resolve it.
        if "easyocr" not in sys.modules:
            sys.modules["easyocr"] = MagicMock()

    def test_implements_ocr_provider(self) -> None:
        from ocr_llm_core._provider import OcrProvider

        self.assertIsInstance(EasyOcrProvider(["en"]), OcrProvider)

    def test_defaults(self) -> None:
        p = EasyOcrProvider(["ch_sim", "en"])
        self.assertEqual(p.lang_list, ["ch_sim", "en"])
        self.assertTrue(p.gpu)

    def test_extract_joins_text_lines(self) -> None:
        p = EasyOcrProvider(["en"])
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = ["line1", "line2", "line3"]
        with patch("easyocr.Reader", return_value=mock_reader):
            result = p.extract(b"fake")
        self.assertEqual(result, "line1\nline2\nline3")

    def test_extract_returns_empty_on_error(self) -> None:
        p = EasyOcrProvider(["en"])
        with patch("easyocr.Reader", side_effect=RuntimeError("no GPU")):
            result = p.extract(b"fake")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
