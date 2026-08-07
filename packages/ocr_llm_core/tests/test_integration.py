"""Integration tests — verify provider registrations via extras."""

from __future__ import annotations

import unittest


class ProviderIntegrationTest(unittest.TestCase):
    def test_all_providers_importable(self) -> None:
        from ocr_llm_core import (
            EasyOcrProvider,
            OcrProvider,
            PaddleVLProvider,
            TesseractProvider,
        )

        self.assertTrue(issubclass(PaddleVLProvider, OcrProvider))
        self.assertTrue(issubclass(TesseractProvider, OcrProvider))
        self.assertTrue(issubclass(EasyOcrProvider, OcrProvider))

    def test_custom_provider(self) -> None:
        """User can implement their own provider."""
        from ocr_llm_core import OcrProvider

        class MyProvider(OcrProvider):
            def extract(self, image_bytes: bytes) -> str:
                return "custom text"

        p = MyProvider()
        self.assertEqual(p.extract(b"anything"), "custom text")


if __name__ == "__main__":
    unittest.main()
