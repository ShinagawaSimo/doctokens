"""Tests for OCR integration in docx_llm_parser."""

from __future__ import annotations

import unittest

from docx_llm_parser.core.models import ParseOptions


class ParseOptionsOcrTest(unittest.TestCase):
    def test_default_ocr_is_none(self) -> None:
        opts = ParseOptions()
        self.assertIsNone(opts.ocr)

    def test_default_ocr_workers(self) -> None:
        opts = ParseOptions()
        self.assertEqual(opts.ocr_workers, 4)

    def test_default_confidence_threshold(self) -> None:
        opts = ParseOptions()
        self.assertEqual(opts.ocr_confidence_threshold, 0.0)

    def test_can_set_ocr_provider(self) -> None:
        from ocr_llm_core import OcrProvider

        class FakeProvider(OcrProvider):
            def extract(self, image_bytes: bytes) -> str:
                return "test"

        p = FakeProvider()
        opts = ParseOptions(
            ocr=p, ocr_workers=2, ocr_confidence_threshold=0.5
        )
        self.assertIs(opts.ocr, p)
        self.assertEqual(opts.ocr_workers, 2)
        self.assertEqual(opts.ocr_confidence_threshold, 0.5)


if __name__ == "__main__":
    unittest.main()
