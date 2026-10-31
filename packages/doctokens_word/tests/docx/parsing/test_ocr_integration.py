"""Tests for OCR integration in doctokens_word."""

from __future__ import annotations

import unittest

from doctokens_word.docx.model import ParseOptions
from ocr_llm_core import OcrResult


class ParseOptionsOcrTest(unittest.TestCase):
    def test_default_ocr_is_none(self) -> None:
        opts = ParseOptions()
        self.assertIsNone(opts.ocr)

    def test_default_ocr_workers(self) -> None:
        opts = ParseOptions()
        self.assertEqual(opts.ocr_workers, 4)
        self.assertEqual(opts.ocr_timeout, 120.0)

    def test_ocr_settings_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "ocr_workers"):
            ParseOptions(ocr_workers=0)
        with self.assertRaisesRegex(ValueError, "ocr_timeout"):
            ParseOptions(ocr_timeout=0)
        with self.assertRaisesRegex(ValueError, "ocr_timeout"):
            ParseOptions(ocr_timeout=True)
        with self.assertRaisesRegex(TypeError, "ocr must provide"):
            ParseOptions(ocr=object())

    def test_can_set_ocr_provider(self) -> None:
        from ocr_llm_core import OcrProvider

        class FakeProvider(OcrProvider):
            def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
                return OcrResult.from_text("test")

        p = FakeProvider()
        opts = ParseOptions(ocr=p, ocr_workers=2)
        self.assertIs(opts.ocr, p)
        self.assertEqual(opts.ocr_workers, 2)


class EndToEndOcrTest(unittest.TestCase):
    def test_media_part_is_read_once_and_read_errors_are_isolated(self) -> None:
        from io import BytesIO

        from doctokens_core.runtime.image_ocr import ImageOcrReader
        from doctokens_word.docx.model import ImageAsset
        from ocr_llm_core import OcrProvider

        class Provider(OcrProvider):
            def __init__(self) -> None:
                self.calls = 0

            def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
                self.calls += 1
                return OcrResult.from_text("read once")

        class Package:
            def __init__(self) -> None:
                self.calls: dict[str, int] = {}

            def open_entry(self, path: str) -> BytesIO:
                self.calls[path] = self.calls.get(path, 0) + 1
                if path == "word/media/broken.png":
                    raise OSError("bad CRC")
                return BytesIO(b"shared image")

        assets: list[ImageAsset] = [
            {"id": "img1", "type": "image", "source": "embedded", "zipPath": "word/media/shared.png"},
            {"id": "img2", "type": "image", "source": "embedded", "zipPath": "word/media/shared.png"},
            {"id": "img3", "type": "image", "source": "embedded", "zipPath": "word/media/broken.png"},
        ]
        provider = Provider()
        package = Package()
        results = {}
        reader = ImageOcrReader(provider, 4, 120.0)
        reader.prepare(
            lambda path: package.open_entry(path).read(), [(asset["id"], asset["zipPath"]) for asset in assets], results, []
        )
        self.assertEqual(package.calls["word/media/shared.png"], 1)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(results["img3"]["error_code"], "image_read_error")

    def test_unrelated_resource_read_does_not_run_ocr(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from _word_fixtures import write_rich_docx
        from doctokens_word import open_docx
        from ocr_llm_core import OcrProvider

        class CountingProvider(OcrProvider):
            def __init__(self) -> None:
                self.calls = 0

            def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
                self.calls += 1
                return OcrResult.from_text("text")

        provider = CountingProvider()
        with TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "test.docx"
            write_rich_docx(docx_path)
            with open_docx(docx_path, options=ParseOptions(ocr=provider)) as document:
                document.render_resource("chart", "chart1")
        self.assertEqual(provider.calls, 0)


if __name__ == "__main__":
    unittest.main()
