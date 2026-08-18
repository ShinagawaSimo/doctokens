"""Contract tests for EasyOcrProvider."""

from __future__ import annotations

import sys
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

from ocr_llm_core._easyocr import EasyOcrProvider
from PIL import Image


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="PNG")
    return output.getvalue()


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
            result = p.extract(_png_bytes())
        self.assertEqual(result, "line1\nline2\nline3")

    def test_extract_returns_empty_on_error(self) -> None:
        p = EasyOcrProvider(["en"])
        with patch("easyocr.Reader", side_effect=RuntimeError("no GPU")):
            result = p.extract(_png_bytes())
        self.assertEqual(result, "")

    def test_extract_result_rejects_pixel_bomb(self) -> None:
        result = EasyOcrProvider(["en"], max_pixels=1).extract_result(_png_bytes())
        self.assertEqual(result.error_code, "image_too_large")

    def test_extract_result_rejects_non_finite_timeout(self) -> None:
        result = EasyOcrProvider(["en"]).extract_result(_png_bytes(), timeout=float("nan"))
        self.assertEqual(result.error_code, "timeout")

    def test_constructor_rejects_boolean_capacity_and_non_boolean_gpu(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_pixels"):
            EasyOcrProvider(["en"], max_pixels=True)
        with self.assertRaisesRegex(TypeError, "gpu"):
            EasyOcrProvider(["en"], gpu="cuda")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
