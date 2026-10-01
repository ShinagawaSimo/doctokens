"""Slide text extraction: runs, soft breaks, tabs, paragraphs, shape order."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

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

    def _plain(self, shapes_xml: str) -> str:
        return parse_pptx(self._deck(shapes_xml), density="plain").text

    def test_runs_concatenate(self) -> None:
        shapes = text_shape_xml([[("t", "Hello"), ("t", " World")]])
        self.assertEqual(self._plain(shapes), "density=plain format=pptx\n=== Slide 1 ===\nHello World")

    def test_soft_break_and_tab(self) -> None:
        shapes = text_shape_xml([[("t", "A"), ("br", ""), ("t", "B"), ("tab", ""), ("t", "C")]])
        self.assertEqual(self._plain(shapes), "density=plain format=pptx\n=== Slide 1 ===\nA\nB\tC")

    def test_empty_and_textless_shapes_are_skipped(self) -> None:
        shapes = text_shape_xml([]) + text_shape_xml([[("t", "Only")]], name="Body")
        self.assertEqual(self._plain(shapes), "density=plain format=pptx\n=== Slide 1 ===\nOnly")

    def test_shape_without_txbody_is_skipped(self) -> None:
        bare = '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Decor"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr/></p:sp>'
        shapes = bare + text_shape_xml([[("t", "Keep")]])
        self.assertEqual(self._plain(shapes), "density=plain format=pptx\n=== Slide 1 ===\nKeep")

    def test_accessible_shape_and_connector_are_retained_in_xml_order(self) -> None:
        def shape_xml(shape_id: int, description: str) -> str:
            return (
                f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Node {shape_id}" descr="{description}"/>'
                "<p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>"
                '<a:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></a:xfrm>'
                '<a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom></p:spPr></p:sp>'
            )

        connector = (
            '<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="4" name="Flow" title="Flow connection"/>'
            "<p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr><p:spPr>"
            '<a:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></a:xfrm>'
            '<a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
            '<a:stCxn id="2" idx="0"/><a:endCxn id="3" idx="0"/>'
            "</p:spPr></p:cxnSp>"
        )
        semantic = parse_pptx(self._deck(shape_xml(2, "Start") + shape_xml(3, "End") + connector), density="semantic").text
        structural = parse_pptx(self._deck(shape_xml(2, "Start") + shape_xml(3, "End") + connector), density="structural").text
        semantic_root = ET.fromstring(semantic)
        connector_node = semantic_root.find(".//shape[@kind='connector']")
        assert connector_node is not None
        self.assertEqual(
            (
                connector_node.get("geometry"),
                connector_node.get("title"),
                connector_node.get("from-shape"),
                connector_node.get("to-shape"),
            ),
            (None, "Flow connection", "s1", "s2"),
        )
        structural_root = ET.fromstring(structural)
        connector_node = structural_root.find(".//shape[@kind='connector']")
        assert connector_node is not None
        self.assertEqual(
            (connector_node.get("id"), connector_node.get("from-shape"), connector_node.get("to-shape")),
            ("s3", "s1", "s2"),
        )


if __name__ == "__main__":
    unittest.main()
