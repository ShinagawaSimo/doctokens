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
from pptx_llm_parser import parse_pptx
from pptx_llm_parser.core.models import ParseOptions, ShapeBlock
from pptx_llm_parser.parser import PptxParser


class SlideTextParsingTests(unittest.TestCase):
    def _deck(self, shapes_xml: str) -> bytes:
        entries = {
            "[Content_Types].xml": content_types_xml(1),
            "_rels/.rels": root_rels_xml(),
            "ppt/presentation.xml": presentation_xml(1),
            "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
            "ppt/slides/slide1.xml": slide_xml_shapes(shapes_xml),
        }
        return make_pptx(entries)

    def _parse(self, shapes_xml: str) -> list[ShapeBlock]:
        parsed = PptxParser().parse(self._deck(shapes_xml), ParseOptions())
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

    def test_accessible_shape_and_connector_are_retained_in_xml_order(self) -> None:
        def shape_xml(shape_id: int, description: str) -> str:
            return (
                f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Node {shape_id}" descr="{description}"/>'
                '<p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
                '<a:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></a:xfrm>'
                '<a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom></p:spPr></p:sp>'
            )

        connector = (
            '<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="4" name="Flow" title="Flow connection"/>'
            '<p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr><p:spPr>'
            '<a:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></a:xfrm>'
            '<a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
            '<a:stCxn id="2" idx="0"/><a:endCxn id="3" idx="0"/>'
            '</p:spPr></p:cxnSp>'
        )
        shapes = self._parse(shape_xml(2, "Start") + shape_xml(3, "End") + connector)
        self.assertEqual([shape["kind"] for shape in shapes], ["roundRect", "roundRect", "connector"])
        self.assertEqual(shapes[2]["fromShape"], shapes[0]["id"])
        self.assertEqual(shapes[2]["toShape"], shapes[1]["id"])
        self.assertEqual(shapes[2]["title"], "Flow connection")
        semantic = parse_pptx(self._deck(shape_xml(2, "Start") + shape_xml(3, "End") + connector), density="semantic")
        structural = parse_pptx(self._deck(shape_xml(2, "Start") + shape_xml(3, "End") + connector), density="structural")
        self.assertIn('<shape kind=connector geometry=line title="Flow connection" from=s1 to=s2', semantic)
        self.assertIn('<shape id=s3 kind=connector title="Flow connection" from=s1 to=s2>', structural)


if __name__ == "__main__":
    unittest.main()
