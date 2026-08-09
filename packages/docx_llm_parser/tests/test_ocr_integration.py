"""Tests for OCR integration in docx_llm_parser."""

from __future__ import annotations

import unittest
from typing import Any, cast

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
        opts = ParseOptions(ocr=p, ocr_workers=2, ocr_confidence_threshold=0.5)
        self.assertIs(opts.ocr, p)
        self.assertEqual(opts.ocr_workers, 2)
        self.assertEqual(opts.ocr_confidence_threshold, 0.5)


class RenderOcrTextTest(unittest.TestCase):
    def test_semantic_output_includes_ocr_text_for_standalone_images(self) -> None:
        """When ParsedDocument has ocr_results, standalone <img> gets <ocr-text> sibling."""
        from docx_llm_parser.core.enums import Density
        from docx_llm_parser.core.models import (
            ContentTypes,
            ImageAsset,
            ParsedDocument,
        )
        from docx_llm_parser.renderers.html5 import to_html5

        assets: list[ImageAsset] = [
            {
                "id": "img1",
                "type": "image",
                "source": "embedded",
                "zipPath": "media/img1.png",
                "contentType": "image/png",
            },
            {
                "id": "img2",
                "type": "image",
                "source": "external",
                "href": "https://example.com/img.jpg",
            },
        ]
        parsed = ParsedDocument(
            metadata={},
            package_info={},
            blocks=[],
            relationships=[],
            styles=[],
            warnings=[],
            assets=assets,
            content_types=ContentTypes(defaults={}, overrides={}),
            ocr_results={"img1": "## Detected text\n\nSome content", "img2": ""},
        )
        html = to_html5(parsed, Density.SEMANTIC)
        # img1 has OCR text
        self.assertIn("<img id=img1>", html)
        self.assertIn("<ocr-text id=img1>## Detected text", html)
        # img2 has empty OCR — error marker
        self.assertIn("<ocr-text id=img2 error>", html)
        # Order: img before ocr-text
        pos_img = html.index("<img id=img1>")
        pos_ocr = html.index("<ocr-text id=img1>")
        self.assertGreater(pos_ocr, pos_img)

    def test_ocr_disabled_no_ocr_text_output(self) -> None:
        """Without ocr_results, no <ocr-text> elements appear."""
        from docx_llm_parser.core.enums import Density
        from docx_llm_parser.core.models import (
            ContentTypes,
            ImageAsset,
            ParsedDocument,
        )
        from docx_llm_parser.renderers.html5 import to_html5

        assets: list[ImageAsset] = [
            {"id": "img1", "type": "image", "source": "embedded", "zipPath": "media/img1.png"},
        ]
        parsed = ParsedDocument(
            metadata={},
            package_info={},
            blocks=[],
            relationships=[],
            styles=[],
            warnings=[],
            assets=assets,
            content_types=ContentTypes(defaults={}, overrides={}),
        )
        html = to_html5(parsed, Density.SEMANTIC)
        self.assertIn("<img id=img1>", html)
        self.assertNotIn("<ocr-text", html)

    def test_inline_image_with_ocr_text(self) -> None:
        """Inline <img> inside a paragraph gets <ocr-text> sibling."""
        from docx_llm_parser.core.enums import Density
        from docx_llm_parser.core.models import (
            ContentTypes,
            ImageAsset,
            ParsedDocument,
        )
        from docx_llm_parser.renderers.html5 import to_html5

        assets: list[ImageAsset] = [
            {"id": "img7", "type": "image", "source": "embedded", "zipPath": "media/img7.png"},
        ]
        block = {
            "id": "b1",
            "type": "paragraph",
            "part": "word/document.xml",
            "order": 0,
            "page": 1,
            "styleId": None,
            "text": "",
            "runs": [{"text": "", "objects": [{"type": "image", "assetId": "img7", "alt": "A diagram"}]}],
        }
        parsed = ParsedDocument(
            metadata={},
            package_info={},
            blocks=cast(Any, [block]),
            relationships=[],
            styles=[],
            warnings=[],
            assets=assets,
            content_types=ContentTypes(defaults={}, overrides={}),
            ocr_results={"img7": "Diagram text"},
        )
        html = to_html5(parsed, Density.SEMANTIC)
        # Inline image rendered inside paragraph block
        self.assertIn("img id=img7", html)
        self.assertIn("ocr-text id=img7>Diagram text", html)


class EndToEndOcrTest(unittest.TestCase):
    def test_full_ocr_pipeline_with_mock_provider(self) -> None:
        """Simulate a complete parse->OCR->render cycle."""
        from pathlib import Path

        from docx_llm_parser import render_document
        from docx_llm_parser.core.models import ParseOptions
        from ocr_llm_core import OcrProvider

        class MarkdownProvider(OcrProvider):
            def extract(self, image_bytes: bytes) -> str:
                return "## Screenshot\n\nThis is OCR extracted text."

        import glob as _g
        import os as _os

        candidates = _g.glob("packages/docx_llm_parser/tests/**/*.docx", recursive=True)
        self.assertTrue(candidates, "No test docx found")
        docx_path = Path(_os.path.abspath(candidates[0]))
        opts = ParseOptions(ocr=MarkdownProvider(), ocr_workers=1)
        html = render_document(docx_path, options=opts)
        self.assertIn("density=semantic", html)
        self.assertIsInstance(html, str)
        self.assertTrue(len(html) > 0)


if __name__ == "__main__":
    unittest.main()
