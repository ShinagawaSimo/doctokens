"""Semantic density rendering: exact output contract with coordinates and inline formats."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import parse_pptx
from pptx_llm_parser.core.enums import Density


class SemanticRenderingTests(unittest.TestCase):
    def test_semantic_output_contract(self) -> None:
        text = parse_pptx(rich_deck_pptx(with_geometry=True), density=Density.SEMANTIC).text
        root = ET.fromstring(text)
        self.assertEqual(root.attrib["density"], "semantic")
        slide_one, slide_two = root.findall("slide")
        self.assertNotIn("z", slide_one.find("title").attrib)
        self.assertEqual(slide_one.find("p").attrib["name"], "Body 2")
        self.assertEqual(slide_one.find("img").attrib["alt"], "Chart photo")
        self.assertNotIn("z", slide_one.find("table").attrib)
        self.assertEqual(slide_one.find("chart").attrib["points"], "4")
        self.assertEqual(slide_one.find("smartart").attrib["name"], "Diagram 8")
        self.assertEqual(slide_one.find("media").attrib["kind"], "video")
        self.assertEqual(slide_two.findtext("p/color/b"), "Secret")


if __name__ == "__main__":
    unittest.main()
