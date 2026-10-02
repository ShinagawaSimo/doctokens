"""End-to-end parser tests using a generated DOCX package."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from _fixtures import write_rich_docx
from docx_llm_parser import open_docx, parse_docx
from docx_llm_parser.core.enums import Density


class DocxPipelineTests(unittest.TestCase):
    def test_parse_render_and_resource_paths(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        docx_path = Path(temporary.name) / "rich.docx"
        write_rich_docx(docx_path)

        # Internal parse for structure assertions
        output = parse_docx(docx_path, density=Density.SEMANTIC).text
        root = ET.fromstring(output)
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
            self.assertTrue(document.read_resource("image", "img1"))
            with self.assertRaisesRegex(ValueError, "read_resource"):
                document.render_resource("image", "img1")
            chart_output = document.render_resource("chart", "chart1").text
            table_output = document.render_resource("table", "t1").text
        assert chart_output is not None
        chart_resource = ET.fromstring(chart_output)
        chart = chart_resource.find(".//chart")
        assert chart is not None
        self.assertEqual(chart.get("type"), "bar")
        self.assertEqual(chart.get("series"), "1")
        assert table_output is not None
        table_resource = ET.fromstring(table_output)
        table = table_resource.find(".//table")
        assert table is not None
        self.assertEqual(table.get("rows"), "2")


if __name__ == "__main__":
    unittest.main()
