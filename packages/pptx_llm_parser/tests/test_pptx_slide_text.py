"""Slide text extraction: runs, soft breaks, tabs, paragraphs, shape order."""

from __future__ import annotations

import unittest

from _pptx_fixtures import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_xml_shapes,
    text_shape_xml,
)
from pptx_llm_parser.core.models import ParseOptions, ShapeBlock
from pptx_llm_parser.parser import PptxParser


class SlideTextParsingTests(unittest.TestCase):
    def _parse(self, shapes_xml: str) -> list[ShapeBlock]:
        entries = {
            "[Content_Types].xml": content_types_xml(1),
            "_rels/.rels": root_rels_xml(),
            "ppt/presentation.xml": presentation_xml(1),
            "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
            "ppt/slides/slide1.xml": slide_xml_shapes(shapes_xml),
        }
        parsed = PptxParser().parse(make_pptx(entries), ParseOptions())
        return parsed.slides[0]["shapes"]

    def test_runs_concatenate(self) -> None:
        shapes = text_shape_xml([[("t", "Hello"), ("t", " World")]])
        self.assertEqual(
            self._parse(shapes),
            [{"id": "s1", "type": "text", "name": "TextBox 1", "text": "Hello World", "z": 1}],
        )

    def test_soft_break_and_tab(self) -> None:
        shapes = text_shape_xml([[("t", "A"), ("br", ""), ("t", "B"), ("tab", ""), ("t", "C")]])
        self.assertEqual(self._parse(shapes)[0]["text"], "A\nB\tC")

    def test_multiple_paragraphs_join_with_newline(self) -> None:
        shapes = text_shape_xml([[("t", "First")], [("t", "Second")]])
        self.assertEqual(self._parse(shapes)[0]["text"], "First\nSecond")

    def test_empty_and_textless_shapes_are_skipped(self) -> None:
        shapes = text_shape_xml([]) + text_shape_xml([[("t", "Only")]], name="Body")
        parsed = self._parse(shapes)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["text"], "Only")

    def test_shape_order_follows_xml(self) -> None:
        shapes = text_shape_xml([[("t", "One")]], name="A") + text_shape_xml([[("t", "Two")]], name="B")
        self.assertEqual([shape["text"] for shape in self._parse(shapes)], ["One", "Two"])

    def test_shape_without_txbody_is_skipped(self) -> None:
        bare = '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Decor"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr/></p:sp>'
        shapes = bare + text_shape_xml([[("t", "Keep")]])
        parsed = self._parse(shapes)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["text"], "Keep")


if __name__ == "__main__":
    unittest.main()
