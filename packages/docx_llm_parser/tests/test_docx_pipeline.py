"""End-to-end parser tests using a generated DOCX package."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from _fixtures import write_rich_docx
from docx_llm_parser.core.enums import RevisionMode
from docx_llm_parser.core.models import ParseOptions
from docx_llm_parser.parsing.runner import DocxParser

from test_support.api_v2_text import Density, parse_docx
from test_support.api_v2_text import render_docx_resource as get_resource
from test_support.api_v2_text import render_docx_window as render_window
from test_support.file_contract import output_path, source_path, write_text_result


class DocxPipelineTests(unittest.TestCase):
    def test_parse_render_query_write_and_batch_paths(self) -> None:
        docx_path = source_path("docx", "pipeline", "rich.docx")
        output_dir = output_path("docx", "pipeline", "parsed.xml").parent
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
        output = parse_docx(docx_path, density=Density.SEMANTIC)
        root = ET.fromstring(output)
        self.assertEqual(root.find(".//h1/color/b").text, "Document Title")
        self.assertEqual(root.find(".//a").get("href"), "https://example.test")
        self.assertEqual(root.find(".//chart").get("id"), "chart1")
        self.assertEqual(root.find(".//smartart").get("type"), "process")
        self.assertEqual(root.find(".//assets/img").get("id"), "img1")
        self.assertIsNotNone(root.find("supplemental"))

        structural_output = parse_docx(docx_path, density=Density.STRUCTURAL)
        plain_text = parse_docx(docx_path, density=Density.PLAIN)
        structural_root = ET.fromstring(structural_output)
        self.assertEqual(structural_root.find(".//chart").get("id"), "chart1")
        self.assertIn("Footnote text", plain_text)
        self.assertIn("Last page", render_window(docx_path, page=-1))

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
        chart_output = get_resource(docx_path, "chart", "chart1")
        self.assertIsNotNone(chart_output)
        assert chart_output is not None
        self.assertIn("type=bar", chart_output)
        table_output = get_resource(docx_path, "table", "t1")
        self.assertIsNotNone(table_output)
        assert table_output is not None
        self.assertIn("rows=2", table_output)

        # Test-side atomic write; production APIs return text/iterators only.
        stale = output_dir / "readable.md"
        stale.write_text("keep", encoding="utf-8")
        output_path_result = write_text_result(output, output_path("docx", "pipeline", "parsed.xml"))
        text_path = write_text_result(plain_text, output_path("docx", "pipeline", "plain.txt"))
        self.assertEqual(output_path_result.name, "parsed.xml")
        self.assertEqual(text_path.name, "plain.txt")
        self.assertEqual(stale.read_text(encoding="utf-8"), "keep")
        self.assertEqual(list(output_dir.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
