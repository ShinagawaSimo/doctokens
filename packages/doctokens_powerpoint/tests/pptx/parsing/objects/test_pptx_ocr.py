"""OCR integration for embedded PPTX pictures."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from _pptx_images import image_deck
from doctokens_powerpoint import parse_pptx
from doctokens_powerpoint.pptx.model.enums import Density
from doctokens_powerpoint.pptx.model.presentation import ParseOptions
from ocr_llm_core import OcrProvider, OcrResult


class _TextProvider(OcrProvider):
    def __init__(self) -> None:
        self.calls = 0

    def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
        self.calls += 1
        return OcrResult.from_text("Slide <text>")


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

    def test_each_one_shot_density_owns_its_ocr_attempt(self) -> None:
        options = ParseOptions(ocr=_TextProvider())
        for density in (Density.SEMANTIC, Density.STRUCTURAL, Density.PLAIN):
            parse_pptx(image_deck(), density=density, options=options)
        self.assertEqual(options.ocr.calls, 3)

    def test_session_recognizes_on_first_body_iteration_and_reuses_across_densities(self) -> None:
        from doctokens_powerpoint import open_pptx

        provider = _TextProvider()
        with open_pptx(image_deck(), options=ParseOptions(ocr=provider)) as presentation:
            self.assertEqual(provider.calls, 0)
            result = presentation.read_resource("image", "img1")
            self.assertEqual(provider.calls, 0)
            iterator = presentation.iter_render(density="plain")
            self.assertEqual(provider.calls, 0)
            next(iterator)
            presentation.render(density="structural")
            presentation.render(density="semantic")
        self.assertTrue(result)
        self.assertEqual(provider.calls, 1)

    def test_external_picture_is_not_downloaded_or_ocrd(self) -> None:
        provider = _TextProvider()
        parse_pptx(image_deck(external=True), options=ParseOptions(ocr=provider))
        self.assertEqual(provider.calls, 0)

    def test_unreferenced_package_image_is_not_ocrd(self) -> None:
        import zipfile
        from io import BytesIO

        source = image_deck()
        input_zip = zipfile.ZipFile(BytesIO(source))
        output = BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in input_zip.namelist():
                archive.writestr(name, input_zip.read(name))
            archive.writestr("ppt/media/unreferenced.png", b"not sent to provider")
        input_zip.close()
        provider = _TextProvider()
        fixture = output.getvalue()
        parse_pptx(fixture, options=ParseOptions(ocr=provider))
        self.assertEqual(provider.calls, 1)

    def test_error_details_stay_internal(self) -> None:
        class ErrorProvider(OcrProvider):
            def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
                return OcrResult.error("engine_error", "private diagnostic")

        options = ParseOptions(ocr=ErrorProvider())
        rendered = parse_pptx(image_deck(), density=Density.SEMANTIC, options=options).text
        root = ET.fromstring(rendered)
        marker = root.find(".//ocr-text")
        self.assertIsNotNone(marker)
        assert marker is not None
        self.assertEqual((marker.get("id"), marker.get("error")), ("img1", "true"))
        self.assertNotIn("private diagnostic", rendered)

    def test_media_read_error_is_isolated(self) -> None:
        class BrokenPackage:
            def read_part(self, path: str) -> bytes:
                raise OSError("bad CRC")

        from doctokens_core.runtime.image_ocr import ImageOcrReader

        provider = _TextProvider()
        results = {}
        ImageOcrReader(provider, 4, 120.0).prepare(
            BrokenPackage().read_part,
            [("img1", "ppt/media/broken.png")],
            results,
            [],
        )
        self.assertEqual(provider.calls, 0)
        self.assertEqual(results["img1"]["error_code"], "image_read_error")


if __name__ == "__main__":
    unittest.main()
