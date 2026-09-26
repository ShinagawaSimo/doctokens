"""Placeholder types, geometry coordinates (per-mille of slide size), and geometric ordering."""

from __future__ import annotations

import unittest
from dataclasses import replace

from _pptx_fixtures import (
    clr_map_xml,
    content_types_xml,
    layout_xml,
    make_pptx,
    master_xml,
    ph_shape_xml,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
    text_shape_xml,
)
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parsing.runner import PptxParser
from pptx_llm_parser.plan import PptxFeature, PptxParsePlan

_SLIDE_LAYOUT_REL = (
    '<Relationship Id="rId10" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
    'Target="../slideLayouts/slideLayout1.xml"/>'
)
_LAYOUT_MASTER_REL = (
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
    'Target="../slideMasters/slideMaster1.xml"/>'
)


def _parse_with_geometry(deck: bytes):
    plan = PptxParsePlan.session()
    return PptxParser().parse(deck, ParseOptions(), plan=replace(plan, features=plan.features | PptxFeature.GEOMETRY))


def _deck(shapes_xml: str, *, layout_shapes: str = "", master_shapes: str = "") -> bytes:
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(
            1,
            extra_defaults=(
                '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
                '<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
            ),
        ),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(shapes_xml),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(_SLIDE_LAYOUT_REL),
        "ppt/slideLayouts/slideLayout1.xml": layout_xml(layout_shapes, clr_map=clr_map_xml()),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": slide_rels_xml(_LAYOUT_MASTER_REL),
        "ppt/slideMasters/slideMaster1.xml": master_xml(master_shapes, clr_map=clr_map_xml()),
    }
    return make_pptx(entries)


class GeometryTests(unittest.TestCase):
    def test_own_geometry_converts_to_per_mille(self) -> None:
        # sldSz 12192000×6858000; off (1219200, 685800) = 10%, ext (2438400, 1371600) = 20%.
        deck = _deck(text_shape_xml([[("t", "A")]], geometry=(1219200, 685800, 2438400, 1371600)))
        parsed = _parse_with_geometry(deck)
        shape = parsed.slides[0]["shapes"][0]
        self.assertEqual((shape["x"], shape["y"], shape["w"], shape["h"]), (100, 100, 200, 200))

    def test_geometry_inherited_from_layout_placeholder(self) -> None:
        deck = _deck(
            text_shape_xml([[("t", "Title")]], ph="title"),
            layout_shapes=ph_shape_xml(idx="0", ph_type="title", geometry=(1219200, 685800, 2438400, 1371600)),
        )
        parsed = _parse_with_geometry(deck)
        shape = parsed.slides[0]["shapes"][0]
        self.assertEqual(shape["placeholderType"], "title")
        self.assertEqual((shape["x"], shape["y"], shape["w"], shape["h"]), (100, 100, 200, 200))

    def test_placeholder_type_from_layout_by_idx(self) -> None:
        deck = _deck(
            text_shape_xml([[("t", "Body")]], ph="body"),
            layout_shapes=ph_shape_xml(idx="0", ph_type="body"),
        )
        parsed = _parse_with_geometry(deck)
        self.assertEqual(parsed.slides[0]["shapes"][0]["placeholderType"], "body")

    def test_shapes_without_geometry_sort_last_keeping_xml_order(self) -> None:
        deck = _deck(
            text_shape_xml([[("t", "Late")]], name="A", shape_id=2)
            + text_shape_xml([[("t", "Early")]], name="B", shape_id=3, geometry=(0, 0, 1000, 1000))
        )
        parsed = _parse_with_geometry(deck)
        self.assertEqual([shape["name"] for shape in parsed.slides[0]["shapes"]], ["B", "A"])

    def test_geometric_sort_by_top_then_left(self) -> None:
        deck = _deck(
            text_shape_xml([[("t", "First")]], name="A", shape_id=2, geometry=(0, 5000, 10, 10))
            + text_shape_xml([[("t", "Second")]], name="B", shape_id=3, geometry=(0, 1000, 10, 10))
            + text_shape_xml([[("t", "Third")]], name="C", shape_id=4, geometry=(3000, 1000, 10, 10))
        )
        parsed = _parse_with_geometry(deck)
        self.assertEqual([shape["name"] for shape in parsed.slides[0]["shapes"]], ["B", "C", "A"])

    def test_stable_sort_keeps_xml_order_for_identical_coordinates(self) -> None:
        deck = _deck(
            text_shape_xml([[("t", "One")]], name="A", shape_id=2, geometry=(0, 0, 10, 10))
            + text_shape_xml([[("t", "Two")]], name="B", shape_id=3, geometry=(0, 0, 10, 10))
        )
        parsed = _parse_with_geometry(deck)
        self.assertEqual([shape["name"] for shape in parsed.slides[0]["shapes"]], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
