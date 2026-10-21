"""Missing layout parts and explicit conflicting clrMap encodings are compatibility exceptions; ordinary intermediate
geometry checks are intentionally omitted.
"""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from _pptx_fixtures import (
    clr_map_xml,
    content_types_xml,
    layout_xml,
    make_pptx,
    master_xml,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
    text_shape_xml,
)
from ooxml_llm_core.relationships import RelationshipIndex
from pptx_llm_parser import parse_pptx
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.core.package import PackageReader
from pptx_llm_parser.ooxml.inheritance import LayoutMasterResolver

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


def _deck(
    *,
    layout_shapes: str = "",
    master_shapes: str = "",
    layout_clr_map: str = "",
    master_clr_map: str = "",
    slide_xml: str | None = None,
) -> bytes:
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
        "ppt/slides/slide1.xml": slide_xml or slide_xml_shapes(text_shape_xml([[("t", "Body")]])),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(_SLIDE_LAYOUT_REL),
        "ppt/slideLayouts/slideLayout1.xml": layout_xml(layout_shapes, clr_map=layout_clr_map),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": slide_rels_xml(_LAYOUT_MASTER_REL),
        "ppt/slideMasters/slideMaster1.xml": master_xml(master_shapes, clr_map=master_clr_map),
    }
    return make_pptx(entries)


def _resolver(deck: bytes) -> tuple[LayoutMasterResolver, PackageReader, ET.Element]:
    pkg = PackageReader(deck, ParseOptions())
    pkg.__enter__()
    relationships = RelationshipIndex.from_records(pkg.read_all_relationships())
    resolver = LayoutMasterResolver(pkg, relationships, [])
    with pkg.open_entry("ppt/slides/slide1.xml") as stream:
        slide_root = ET.parse(stream).getroot()
    return resolver, pkg, slide_root


class LayoutMasterResolverTests(unittest.TestCase):
    def test_list_inheritance_does_not_parse_malformed_visual_defaults_in_low_densities(self) -> None:
        # The invalid master RGB is a producer-corruption case. List content
        # remains readable without enabling the semantic color decoder.
        master = (
            '<p:txStyles><p:bodyStyle><a:lvl1pPr><a:buChar char="M"/>'
            '<a:defRPr><a:solidFill><a:srgbClr val="invalid"/></a:solidFill></a:defRPr>'
            "</a:lvl1pPr></p:bodyStyle></p:txStyles>"
        )
        for declaration, expected in (
            ('<a:buAutoNum type="romanLcParenR" startAt="3"/>', "iii) One\niv) Two"),
            ("<a:buNone/>", "One\nTwo"),
        ):
            layout = text_shape_xml([], ph="body").replace(
                "<a:lstStyle/>", f"<a:lstStyle><a:lvl1pPr>{declaration}</a:lvl1pPr></a:lstStyle>"
            )
            source = _deck(
                layout_shapes=layout,
                master_clr_map=master,
                slide_xml=slide_xml_shapes(text_shape_xml([[("t", "One")], [("t", "Two")]], ph="body")),
            )
            for density in ("plain", "structural", "semantic"):
                with self.subTest(declaration=declaration, density=density):
                    result = parse_pptx(source, density=density)
                    if density == "plain":
                        self.assertEqual(result.text, "density=plain format=pptx\n=== Slide 1 ===\n" + expected)
                    else:
                        attrs = 'placeholder="body" shape-id="s1"'
                        if density == "semantic":
                            attrs = 'id="s1" name="TextBox 1" ' + attrs
                        self.assertEqual(
                            result.text,
                            f'<presentation density="{density}" format="pptx"><slide number="1"><p {attrs}>'
                            + expected
                            + "</p></slide></presentation>",
                        )
                    if density != "semantic":
                        self.assertNotIn("COLOR_VALUE_INVALID", [warning.code for warning in result.report.warnings])

    def test_missing_layout_yields_warning_and_empty_context(self) -> None:
        entries: dict[str, str | bytes] = {
            "[Content_Types].xml": content_types_xml(1),
            "_rels/.rels": root_rels_xml(),
            "ppt/presentation.xml": presentation_xml(1),
            "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
            "ppt/slides/slide1.xml": slide_xml_shapes(text_shape_xml([[("t", "Body")]])),
            "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(_SLIDE_LAYOUT_REL),
        }
        warnings: list = []
        pkg = PackageReader(make_pptx(entries), ParseOptions())
        pkg.__enter__()
        try:
            relationships = RelationshipIndex.from_records(pkg.read_all_relationships())
            resolver = LayoutMasterResolver(pkg, relationships, warnings)
            with pkg.open_entry("ppt/slides/slide1.xml") as stream:
                root = ET.parse(stream).getroot()
            resolver.resolve("ppt/slides/slide1.xml", root)
        finally:
            pkg.__exit__(None, None, None)
        self.assertTrue(any(w.code == "LAYOUT_PART_MISSING" for w in warnings))

    def test_clr_map_merge_slide_over_layout_over_master_over_default(self) -> None:
        deck = _deck(
            layout_clr_map=clr_map_xml(accent1="accent3"),
            master_clr_map=clr_map_xml(accent1="accent2", tx1="dk2"),
            slide_xml=(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                '<p:clrMapOvr><a:overrideClrMapping xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'tx1="lt1"/></p:clrMapOvr>'
                "<p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/></p:spTree></p:cSld></p:sld>"
            ),
        )
        resolver, pkg, root = _resolver(deck)
        try:
            color_map = resolver.resolve("ppt/slides/slide1.xml", root)["color_map"]
        finally:
            pkg.__exit__(None, None, None)
        self.assertEqual(color_map["accent1"], "accent3")  # layout beats master
        self.assertEqual(color_map["tx1"], "lt1")  # slide override beats everything
        self.assertEqual(color_map["accent2"], "accent2")  # default identity


if __name__ == "__main__":
    unittest.main()
