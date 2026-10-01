"""Tests for OCR integration in docx_llm_parser."""

from __future__ import annotations

import unittest
from typing import Any, cast
from xml.etree import ElementTree as ET

from docx_llm_parser.core.models import ParseOptions


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
            def extract(self, image_bytes: bytes) -> str:
                return "test"

        p = FakeProvider()
        opts = ParseOptions(ocr=p, ocr_workers=2)
        self.assertIs(opts.ocr, p)
        self.assertEqual(opts.ocr_workers, 2)


class RenderOcrTextTest(unittest.TestCase):
    def test_semantic_output_includes_ocr_text_for_standalone_images(self) -> None:
        """When ParsedDocument has ocr_results, standalone <img> gets <ocr-text> sibling."""
        from docx_llm_parser.core.enums import Density
        from docx_llm_parser.core.models import (
            ContentTypes,
            ImageAsset,
            ParsedDocument,
        )
        from docx_llm_parser.rendering.dispatch import to_output

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
        root = ET.fromstring(to_output(parsed, Density.SEMANTIC))
        assets = root.find("assets")
        self.assertIsNotNone(assets)
        assert assets is not None
        self.assertEqual([item.tag for item in assets], ["img", "ocr-text", "img", "ocr-text"])
        self.assertEqual(assets[0].get("id"), "img1")
        self.assertTrue((assets[1].text or "").startswith("## Detected text"))
        self.assertEqual((assets[3].get("id"), assets[3].get("error")), ("img2", "true"))

    def test_structured_ocr_results_escape_text_and_preserve_empty(self) -> None:
        from docx_llm_parser.core.enums import Density
        from docx_llm_parser.core.models import ContentTypes, ImageAsset, ParsedDocument
        from docx_llm_parser.rendering.dispatch import to_output

        assets: list[ImageAsset] = [
            {"id": "img1", "type": "image", "source": "embedded", "zipPath": "media/1.png"},
            {"id": "img2", "type": "image", "source": "embedded", "zipPath": "media/2.png"},
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
            ocr_results={
                "img1": {"status": "success", "text": "A < B"},
                "img2": {"status": "empty", "text": ""},
            },
        )
        root = ET.fromstring(to_output(parsed, Density.SEMANTIC))
        first, second = root.findall(".//assets/ocr-text")
        self.assertEqual((first.get("id"), first.text), ("img1", "A < B"))
        self.assertEqual((second.get("id"), second.get("empty")), ("img2", "true"))

    def test_ocr_disabled_no_ocr_text_output(self) -> None:
        """Without ocr_results, no <ocr-text> elements appear."""
        from docx_llm_parser.core.enums import Density
        from docx_llm_parser.core.models import (
            ContentTypes,
            ImageAsset,
            ParsedDocument,
        )
        from docx_llm_parser.rendering.dispatch import to_output

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
        root = ET.fromstring(to_output(parsed, Density.SEMANTIC))
        self.assertEqual(root.find(".//assets/img").get("id"), "img1")
        self.assertEqual(root.findall(".//ocr-text"), [])

    def test_inline_image_with_ocr_text(self) -> None:
        """Inline <img> inside a paragraph gets <ocr-text> sibling."""
        from docx_llm_parser.core.enums import Density
        from docx_llm_parser.core.models import (
            ContentTypes,
            ImageAsset,
            ParsedDocument,
        )
        from docx_llm_parser.rendering.dispatch import to_output

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
        root = ET.fromstring(to_output(parsed, Density.SEMANTIC))
        paragraph = root.find(".//body/p")
        self.assertIsNotNone(paragraph)
        assert paragraph is not None
        self.assertEqual([item.tag for item in paragraph], ["img", "ocr-text"])
        self.assertEqual((paragraph[0].get("id"), paragraph[1].text), ("img7", "Diagram text"))

    def test_nested_table_image_receives_ocr_in_semantic_and_plain_output(self) -> None:
        from docx_llm_parser.core.enums import Density
        from docx_llm_parser.core.models import ContentTypes, ImageAsset, ParsedDocument
        from docx_llm_parser.rendering.dispatch import to_output

        image_paragraph = {
            "id": "p1",
            "type": "paragraph",
            "part": "word/document.xml",
            "order": 0,
            "page": 1,
            "styleId": None,
            "text": "",
            "runs": [{"text": "", "objects": [{"type": "image", "assetId": "img-table"}]}],
        }
        inner_table = {
            "id": "inner",
            "type": "table",
            "tableId": "table-inner",
            "columnCount": 1,
            "rows": [
                {
                    "isHeader": False,
                    "cells": [
                        {
                            "text": "",
                            "colSpan": 1,
                            "rowSpan": 1,
                            "blocks": [image_paragraph],
                        }
                    ],
                }
            ],
        }
        outer_table = {
            "id": "outer",
            "type": "table",
            "tableId": "table-outer",
            "columnCount": 1,
            "rows": [
                {
                    "isHeader": False,
                    "cells": [{"text": "", "colSpan": 1, "rowSpan": 1, "blocks": [inner_table]}],
                }
            ],
        }
        assets: list[ImageAsset] = [{"id": "img-table", "type": "image", "source": "embedded", "zipPath": "media/table.png"}]
        parsed = ParsedDocument(
            metadata={},
            package_info={},
            blocks=cast(Any, [outer_table]),
            relationships=[],
            styles=[],
            warnings=[],
            assets=assets,
            content_types=ContentTypes(defaults={}, overrides={}),
            ocr_results={"img-table": {"status": "success", "text": "Cell OCR"}},
        )
        semantic = to_output(parsed, Density.SEMANTIC)
        plain = to_output(parsed, Density.PLAIN)
        semantic_root = ET.fromstring(semantic)
        self.assertTrue(any(item.text == "Cell OCR" for item in semantic_root.findall(".//ocr-text")))
        self.assertIn("OCR: Cell OCR", plain)

    def test_supplemental_image_receives_ocr(self) -> None:
        from docx_llm_parser.core.enums import Density
        from docx_llm_parser.core.models import ContentTypes, ParsedDocument
        from docx_llm_parser.rendering.dispatch import to_output

        header = {
            "id": "header1",
            "loc": "header",
            "text": "",
            "runs": [{"text": "", "objects": [{"type": "image", "assetId": "img-header"}]}],
        }
        parsed = ParsedDocument(
            metadata={},
            package_info={},
            blocks=[],
            relationships=[],
            styles=[],
            warnings=[],
            assets=[],
            content_types=ContentTypes(defaults={}, overrides={}),
            headers=cast(Any, [header]),
            ocr_results={"img-header": {"status": "success", "text": "Header OCR"}},
        )
        semantic = to_output(parsed, Density.SEMANTIC)
        semantic_root = ET.fromstring(semantic)
        self.assertEqual(semantic_root.findtext(".//headers/header/ocr-text"), "Header OCR")


class EndToEndOcrTest(unittest.TestCase):
    def test_media_part_is_read_once_and_read_errors_are_isolated(self) -> None:
        from io import BytesIO

        from docx_llm_parser.core.models import ImageAsset, ParseOptions
        from docx_llm_parser.parsing.runner import DocxParser
        from ocr_llm_core import OcrProvider

        class Provider(OcrProvider):
            def __init__(self) -> None:
                self.calls = 0

            def extract(self, image_bytes: bytes) -> str:
                self.calls += 1
                return "read once"

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
        results = DocxParser._run_ocr(cast(Any, package), assets, ParseOptions(ocr=provider))
        self.assertEqual(package.calls["word/media/shared.png"], 1)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(results["img3"]["error_code"], "image_read_error")

    def test_session_with_ocr_provider_runs_ocr_before_resource_reads(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from _fixtures import write_rich_docx
        from docx_llm_parser import open_docx
        from ocr_llm_core import OcrProvider

        class CountingProvider(OcrProvider):
            def __init__(self) -> None:
                self.calls = 0

            def extract(self, image_bytes: bytes) -> str:
                self.calls += 1
                return "text"

        provider = CountingProvider()
        with TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "test.docx"
            write_rich_docx(docx_path)
            with open_docx(docx_path, options=ParseOptions(ocr=provider)) as document:
                document.render_resource("chart", "chart1")
        self.assertEqual(provider.calls, 1)


if __name__ == "__main__":
    unittest.main()
