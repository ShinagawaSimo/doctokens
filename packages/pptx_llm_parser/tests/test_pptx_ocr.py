"""OCR integration for embedded PPTX pictures."""

from __future__ import annotations

import unittest
from typing import Any, cast

from _pptx_fixtures import PNG_BYTES
from ocr_llm_core import OcrProvider, OcrResult
from pptx_llm_parser import Density, parse_pptx
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parser import PptxParser
from test_pptx_images import _image_deck

from test_support.file_contract import materialize_bytes


class _TextProvider(OcrProvider):
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, image_bytes: bytes) -> str:
        self.calls += 1
        return "Slide <text>"


class PptxOcrTests(unittest.TestCase):
    def test_parse_options_validate_ocr_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "ocr_workers"):
            ParseOptions(ocr_workers=0)
        with self.assertRaisesRegex(ValueError, "ocr_timeout"):
            ParseOptions(ocr_timeout=0)
        with self.assertRaisesRegex(ValueError, "ocr_timeout"):
            ParseOptions(ocr_timeout=True)
        with self.assertRaisesRegex(TypeError, "ocr must provide"):
            ParseOptions(ocr=object())

    def test_embedded_picture_is_ocrd_once_and_stored_by_asset_id(self) -> None:
        provider = _TextProvider()
        parsed = PptxParser().parse(_image_deck(), ParseOptions(ocr=provider))
        self.assertEqual(provider.calls, 1)
        self.assertEqual(parsed.ocr_results["img1"]["status"], "success")
        self.assertEqual(parsed.ocr_results["img1"]["text"], "Slide <text>")

    def test_semantic_emits_escaped_ocr_sibling_only(self) -> None:
        options = ParseOptions(ocr=_TextProvider())
        semantic = parse_pptx(_image_deck(), density=Density.SEMANTIC, options=options)
        structural = parse_pptx(_image_deck(), density=Density.STRUCTURAL, options=options)
        plain = parse_pptx(_image_deck(), density=Density.PLAIN, options=options)
        self.assertEqual(options.ocr.calls, 1)
        self.assertIn("<img id=img1", semantic)
        self.assertIn("<ocr-text id=img1>Slide &lt;text&gt;", semantic)
        self.assertNotIn("<ocr-text", structural)
        self.assertNotIn("Slide <text>", plain)

    def test_resource_query_does_not_trigger_ocr(self) -> None:
        from pptx_llm_parser import get_resource

        provider = _TextProvider()
        result = get_resource(_image_deck(), "image", "img1", options=ParseOptions(ocr=provider))
        self.assertIsNotNone(result)
        self.assertEqual(provider.calls, 0)

    def test_external_picture_is_not_downloaded_or_ocrd(self) -> None:
        provider = _TextProvider()
        parsed = PptxParser().parse(_image_deck(external=True), ParseOptions(ocr=provider))
        self.assertEqual(provider.calls, 0)
        self.assertEqual(parsed.ocr_results, {})

    def test_unreferenced_package_image_is_not_ocrd(self) -> None:
        import zipfile
        from io import BytesIO

        source = _image_deck()
        input_zip = zipfile.ZipFile(source)
        output = BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in input_zip.namelist():
                archive.writestr(name, input_zip.read(name))
            archive.writestr("ppt/media/unreferenced.png", b"not sent to provider")
        input_zip.close()
        provider = _TextProvider()
        fixture = materialize_bytes(output.getvalue(), suffix=".pptx", package="pptx", name="ocr-unreferenced-image")
        PptxParser().parse(fixture, ParseOptions(ocr=provider))
        self.assertEqual(provider.calls, 1)

    def test_error_details_stay_internal(self) -> None:
        class ErrorProvider(OcrProvider):
            def extract(self, image_bytes: bytes) -> str:
                return ""

            def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
                return OcrResult.error("engine_error", "private diagnostic")

        options = ParseOptions(ocr=ErrorProvider())
        parsed = PptxParser().parse(_image_deck(), options)
        self.assertEqual(parsed.ocr_results["img1"]["error_message"], "private diagnostic")
        rendered = parse_pptx(_image_deck(), density=Density.SEMANTIC, options=options)
        self.assertIn("<ocr-text id=img1 error>", rendered)
        self.assertNotIn("private diagnostic", rendered)

    def test_media_read_error_is_isolated(self) -> None:
        class BrokenPackage:
            def open_entry(self, path: str) -> object:
                raise OSError("bad CRC")

        provider = _TextProvider()
        assets = [
            {
                "id": "img1",
                "type": "image",
                "source": "embedded",
                "zipPath": "ppt/media/broken.png",
            }
        ]
        slides = [
            {
                "id": "slide1",
                "type": "slide",
                "n": 1,
                "part": "ppt/slides/slide1.xml",
                "sldId": "256",
                "hidden": False,
                "shapes": [{"id": "shape1", "type": "picture", "assetId": "img1"}],
                "notes": None,
            }
        ]
        results = PptxParser._run_ocr(
            cast(Any, BrokenPackage()),
            cast(Any, assets),
            cast(Any, slides),
            ParseOptions(ocr=provider),
        )
        self.assertEqual(provider.calls, 0)
        self.assertEqual(results["img1"]["error_code"], "image_read_error")

    def test_fixture_is_a_supported_png(self) -> None:
        import base64

        self.assertTrue(base64.b64decode(PNG_BYTES).startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
