"""Regression coverage for the user-provided Word style fixture."""

from __future__ import annotations

import unittest
from pathlib import Path

from docx_llm_parser import Density, parse_docx
from docx_llm_parser.core.models import ParseOptions
from docx_llm_parser.parser import DocxParser

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

    def test_rendered_html_keeps_non_heading_styles_as_paragraphs(self) -> None:
        semantic = parse_docx(FIXTURE, density=Density.SEMANTIC)
        self.assertIn("<h6><b><color value=#2F5496>Title 6</color>", semantic)
        self.assertIn("<h7><b><color value=#595959>Title 7</color>", semantic)
        self.assertIn("<h9><color value=#595959>Title 9</color>", semantic)
        self.assertIn("<p align=center>Title\n", semantic)
        self.assertIn(
            "<p align=center border-top=single:#2F5496 border-bottom=single:#2F5496>"
            "<i><color value=#2F5496>Conspicuously citation</color>",
            semantic,
        )
        self.assertIn("<smallcaps><color value=#5A5A5A>Inconspicuously reference</color></smallcaps>", semantic)


if __name__ == "__main__":
    unittest.main()
