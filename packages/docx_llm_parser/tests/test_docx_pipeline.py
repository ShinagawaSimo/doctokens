"""End-to-end parser tests using a generated DOCX package."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from _fixtures import write_rich_docx
from docx_llm_parser import open_docx, parse_docx
from docx_llm_parser.core.enums import Density, RevisionMode
from docx_llm_parser.core.models import ParseOptions
from docx_llm_parser.parsing.runner import DocxParser


class DocxPipelineTests(unittest.TestCase):
    def test_parse_render_and_resource_paths(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        docx_path = Path(temporary.name) / "rich.docx"
        write_rich_docx(docx_path)

        # Internal parse for structure assertions
        parsed = DocxParser().parse(
            docx_path,
            ParseOptions(
                revision_mode=RevisionMode.REVIEW,
            ),
        )

        self.assertEqual(parsed.metadata["sourceFile"], "rich.docx")
        self.assertEqual(parsed.package_info["entryCount"], 15)
        self.assertEqual(len(parsed.assets), 1)
        self.assertEqual(parsed.assets[0]["contentType"], "image/png")
        self.assertEqual(parsed.charts[0]["chartType"], "bar")
        self.assertEqual(parsed.smartarts[0]["layoutType"], "process")
        self.assertEqual(parsed.headers[0]["text"], "Header text")
        self.assertEqual(parsed.footers[0]["text"], "Footer text")
        self.assertEqual(parsed.footnotes[0]["text"], "Footnote text")
        self.assertEqual(parsed.endnotes[0]["text"], "Endnote text")
        self.assertEqual(parsed.comments[0]["author"], "Reviewer")
        self.assertIn("paragraphCount", parsed.metrics["counters"])

        # Public API: render
        output = parse_docx(docx_path, density=Density.SEMANTIC).text
        root = ET.fromstring(output)
        self.assertEqual(root.find(".//h1/color/b").text, "Document Title")
        self.assertEqual(root.find(".//a").get("href"), "https://example.test")
        self.assertEqual(root.find(".//chart").get("id"), "chart1")
        self.assertEqual(root.find(".//smartart").get("type"), "process")
        self.assertEqual(root.find(".//assets/img").get("id"), "img1")
        self.assertIsNotNone(root.find("supplemental"))

        structural_output = parse_docx(docx_path, density=Density.STRUCTURAL).text
        plain_text = parse_docx(docx_path, density=Density.PLAIN).text
        structural_root = ET.fromstring(structural_output)
        self.assertEqual(structural_root.find(".//chart").get("id"), "chart1")
        self.assertIn("Footnote text", plain_text)
        self.assertIn("Last page", parse_docx(docx_path, page_hint=-1).text)

        # structural: no headers/footers; notes and comments remain.
        self.assertNotIn("Header text", structural_output)
        self.assertNotIn("Footer text", structural_output)
        self.assertIsNotNone(structural_root.find(".//footnotes/footnote"))
        self.assertIsNotNone(structural_root.find(".//comments/comment"))

        # Plain density: headers/footers excluded, comments retained.
        self.assertNotIn("[Headers]", plain_text)
        self.assertNotIn("[Footers]", plain_text)
        self.assertNotIn("Header text", plain_text)
        self.assertIn("[Comments]", plain_text)
        self.assertIn("Comment text", plain_text)

        # Public API: resource extraction
        with open_docx(docx_path) as document:
            chart_output = document.render_resource("chart", "chart1").text
            table_output = document.render_resource("table", "t1").text
        self.assertIsNotNone(chart_output)
        assert chart_output is not None
        self.assertIn("type=bar", chart_output)
        self.assertIsNotNone(table_output)
        assert table_output is not None
        self.assertIn("rows=2", table_output)


if __name__ == "__main__":
    unittest.main()
