"""Contract tests for TesseractProvider."""

from __future__ import annotations

import sys
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

from ocr_llm_core.providers.tesseract import TesseractProvider
from PIL import Image


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="PNG")
    return output.getvalue()


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
        from ocr_llm_core.models import OcrProvider

        self.assertIsInstance(TesseractProvider(), OcrProvider)

    def test_defaults(self) -> None:
        p = TesseractProvider()
        self.assertEqual(p.lang, "eng")
        self.assertIsNone(p.tesseract_cmd)

    def test_extract_calls_image_to_string(self) -> None:
        p = TesseractProvider(lang="eng+chi_sim")
        with patch("pytesseract.image_to_string", return_value="hello world"):
            result = p.extract_result(_png_bytes())
        self.assertEqual(result.text, "hello world")

    def test_multiple_output_preserves_text_and_normalizes_word_scores(self) -> None:
        # Mock engine transport supplies exact TSV scores; public records keep
        # only the low-confidence hint, independently of TXT formatting.
        text = "A\n\ncomplete text"
        tsv = "text\tconf\nA\t20\ncomplete\t60\ntext\t70\n"
        with patch("pytesseract.run_and_get_multiple_output", return_value=[text, tsv], create=True):
            result = TesseractProvider().extract_result(_png_bytes())
        self.assertEqual(result.text, text)
        self.assertTrue(result.to_record()["low_confidence"])
        self.assertNotIn("confidence", result.to_record())

    def test_extract_returns_empty_on_error(self) -> None:
        p = TesseractProvider()
        with patch(
            "pytesseract.image_to_string",
            side_effect=RuntimeError("tesseract not found"),
        ):
            result = p.extract_result(_png_bytes())
        self.assertEqual(result.text, "")

    def test_pytesseract_runtime_timeout_is_classified(self) -> None:
        p = TesseractProvider()
        with patch("pytesseract.image_to_string", side_effect=RuntimeError("Tesseract process timeout")):
            result = p.extract_result(_png_bytes(), timeout=0.1)
        self.assertEqual(result.error_code, "timeout")

    def test_extract_result_rejects_non_finite_timeout(self) -> None:
        result = TesseractProvider().extract_result(_png_bytes(), timeout=float("inf"))
        self.assertEqual(result.error_code, "timeout")

    def test_constructor_rejects_invalid_strings_and_boolean_capacity(self) -> None:
        with self.assertRaisesRegex(ValueError, "lang"):
            TesseractProvider(lang=" ")
        with self.assertRaisesRegex(ValueError, "tesseract_cmd"):
            TesseractProvider(tesseract_cmd=" ")
        with self.assertRaisesRegex(ValueError, "max_input_bytes"):
            TesseractProvider(max_input_bytes=True)

    def test_tesseract_command_is_restored(self) -> None:
        p = TesseractProvider(tesseract_cmd="custom-tesseract")
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = "original-tesseract"
        with patch("pytesseract.image_to_string", return_value="ok"):
            p.extract_result(_png_bytes())
        self.assertEqual(pytesseract.pytesseract.tesseract_cmd, "original-tesseract")


if __name__ == "__main__":
    unittest.main()
