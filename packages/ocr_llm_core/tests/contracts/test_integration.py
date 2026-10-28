"""Integration tests — verify provider registrations via extras."""

from __future__ import annotations

import unittest

from ocr_llm_core import OcrResult


class ProviderIntegrationTest(unittest.TestCase):
    def test_all_providers_importable(self) -> None:
        from ocr_llm_core import EasyOcrProvider, OcrProvider, PaddleVLProvider, TesseractProvider

        self.assertTrue(issubclass(PaddleVLProvider, OcrProvider))
        self.assertTrue(issubclass(TesseractProvider, OcrProvider))
        self.assertTrue(issubclass(EasyOcrProvider, OcrProvider))

    def test_custom_provider(self) -> None:
        """User can implement their own provider."""
        from ocr_llm_core import OcrProvider

        class MyProvider(OcrProvider):
            def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
                return OcrResult.from_text("custom text")

        p = MyProvider()
        self.assertEqual(p.extract_result(b"anything").text, "custom text")


if __name__ == "__main__":
    unittest.main()
