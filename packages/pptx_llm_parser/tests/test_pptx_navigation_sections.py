"""Named sections and shape-level navigation actions."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from _pptx_fixtures import (
    P14_NS,
    P_NS,
    R_NS,
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
    text_shape_xml,
)

from test_support.api_v2_text import parse_pptx


class NavigationAndSectionsTests(unittest.TestCase):
    def test_sections_and_shape_actions_resolve_to_slide_anchors(self) -> None:
        button = text_shape_xml([[("t", "Go")]], name="Go", shape_id=2).replace(
            '<p:cNvPr id="2" name="Go"/>',
            '<p:cNvPr id="2" name="Go"><a:hlinkClick r:id="rIdJump"/></p:cNvPr>',
        )
        presentation = f"""<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}" xmlns:p14="{P14_NS}">
          <p:sldIdLst><p:sldId id="256" r:id="rId1"/><p:sldId id="257" r:id="rId2"/></p:sldIdLst>
          <p:sldSz cx="12192000" cy="6858000"/>
          <p:extLst><p:ext uri="{{521415D9-36F7-43E2-AB2F-B90AF26B5E84}}"><p14:sectionLst>
            <p14:section name="Intro"><p14:sldIdLst><p14:sldId id="256"/></p14:sldIdLst></p14:section>
            <p14:section name="Details"><p14:sldIdLst><p14:sldId id="257"/></p14:sldIdLst></p14:section>
          </p14:sectionLst></p:ext></p:extLst>
        </p:presentation>"""
        data = make_pptx(
            {
                "[Content_Types].xml": content_types_xml(2),
                "_rels/.rels": root_rels_xml(),
                "ppt/presentation.xml": presentation,
                "ppt/_rels/presentation.xml.rels": presentation_rels_xml(2),
                "ppt/slides/slide1.xml": slide_xml_shapes(button),
                "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(
                    '<Relationship Id="rIdJump" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
                    'Target="slide2.xml"/>'
                ),
                "ppt/slides/slide2.xml": slide_xml_shapes(text_shape_xml([[("t", "Target")]], shape_id=2)),
            }
        )
        structural = parse_pptx(data, density="structural")
        root = ET.fromstring(structural)
        self.assertEqual(
            [(item.get("number"), item.get("section")) for item in root.findall("slide")],
            [("1", "Intro"), ("2", "Details")],
        )
        self.assertEqual(root.find(".//slide/p").get("link"), "#slide2")

        plain = parse_pptx(data, density="plain")
        self.assertIn("=== Slide 1 (Section: Intro) ===", plain)


if __name__ == "__main__":
    unittest.main()
