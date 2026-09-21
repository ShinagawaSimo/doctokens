"""Regression coverage for the user-provided Word style fixture."""

from __future__ import annotations

import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from docx_llm_parser.core.models import ParseOptions
from docx_llm_parser.parsing.runner import DocxParser

from test_support.api_v2_text import Density, parse_docx

FIXTURE = Path(__file__).resolve().parents[3] / "test_support" / "fixtures" / "docx" / "docx-heading-style.docx"


class HeadingStyleFileTests(unittest.TestCase):
    def test_heading_style_format_applies_to_runs_without_direct_rpr(self) -> None:
        parsed = DocxParser().parse(FIXTURE, ParseOptions())
        title6 = parsed.blocks[5]

        self.assertEqual(title6["type"], "heading")
        self.assertEqual(title6["level"], 6)
        self.assertEqual("".join(run["text"] for run in title6["runs"]), "Title 6")
        self.assertTrue(all(run.get("format", {}).get("bold") for run in title6["runs"]))
        self.assertTrue(all(run.get("format", {}).get("color") == "#2F5496" for run in title6["runs"]))

    def test_outline_levels_seven_through_nine_are_preserved_in_model(self) -> None:
        parsed = DocxParser().parse(FIXTURE, ParseOptions())
        self.assertEqual([block["level"] for block in parsed.blocks[5:9]], [6, 7, 8, 9])

    def test_rendered_output_keeps_non_heading_styles_as_paragraphs(self) -> None:
        semantic = parse_docx(FIXTURE, density=Density.SEMANTIC)
        root = ET.fromstring(semantic)
        self.assertEqual(root.findtext(".//h6/color/b"), "Title 6")
        self.assertEqual(root.findtext(".//h7/color/b"), "Title 7")
        self.assertEqual(root.findtext(".//h9/color"), "Title 9")
        self.assertEqual(root.find(".//p[@align='center']").text, "Title")
        citation = root.find(".//p[@border-top='single:#2F5496']/color/i")
        self.assertEqual(citation.text if citation is not None else None, "Conspicuously citation")
        self.assertEqual(root.findtext(".//small-caps"), "Inconspicuously reference")


if __name__ == "__main__":
    unittest.main()
