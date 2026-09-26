"""Structural density rendering: exact output contract."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import parse_pptx
from pptx_llm_parser.core.enums import Density


class StructuralRenderingTests(unittest.TestCase):
    def test_structural_output_contract(self) -> None:
        text = parse_pptx(rich_deck_pptx(), density=Density.STRUCTURAL).text
        root = ET.fromstring(text)
        self.assertEqual(root.attrib["density"], "structural")
        slide_one, slide_two = root.findall("slide")
        self.assertEqual(slide_one.findtext("title"), "Title")
        self.assertEqual(slide_one.find("p/a").get("href"), "https://example.test/doc")
        self.assertEqual(slide_one.find("img").get("id"), "img1")
        self.assertEqual([[cell.text for cell in row] for row in slide_one.findall("table/tr")], [["A", "B"], ["C", "D"]])
        self.assertEqual(slide_one.find("chart").get("truncated"), "true")
        self.assertEqual(slide_one.findtext("smartart"), "Start Middle End")
        self.assertEqual(slide_one.findtext("speaker-notes"), "Talk")
        self.assertEqual(slide_two.get("hidden"), "true")
        self.assertEqual([item.get("id") for item in root.findall("comments/comment")], ["cmt1", "cmt2"])


if __name__ == "__main__":
    unittest.main()
