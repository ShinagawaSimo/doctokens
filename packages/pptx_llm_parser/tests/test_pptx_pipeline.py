"""End-to-end plain rendering through the public API."""

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
from pptx_llm_parser import open_pptx, parse_pptx
from pptx_llm_parser.core.enums import Density


def _two_slide_deck() -> bytes:
    slide1 = slide_xml_shapes(
        text_shape_xml([[("t", "Title")]], name="Title 1")
        + text_shape_xml([[("t", "Point one")], [("t", "Point two")]], name="Body 2")
    )
    slide2 = slide_xml_shapes(text_shape_xml([[("t", "Secret")]], name="Title 1"), hidden=True)
    entries = {
        "[Content_Types].xml": content_types_xml(2),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(2),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(2),
        "ppt/slides/slide1.xml": slide1,
        "ppt/slides/slide2.xml": slide2,
    }
    return make_pptx(entries)


class PlainPipelineTests(unittest.TestCase):
    def test_plain_starts_with_density_marker(self) -> None:
        text = parse_pptx(_two_slide_deck(), density=Density.PLAIN).text
        self.assertEqual(text.splitlines()[0], "density=plain format=pptx syntax=doctokens-plain/1.0")

    def test_plain_separates_slides(self) -> None:
        text = parse_pptx(_two_slide_deck(), density=Density.PLAIN).text
        self.assertIn("=== Slide 1 ===", text)
        self.assertIn("=== Slide 2 ===", text)

    def test_plain_includes_hidden_slide_text(self) -> None:
        text = parse_pptx(_two_slide_deck(), density=Density.PLAIN).text
        self.assertIn("Secret", text)

    def test_plain_shape_layout(self) -> None:
        text = parse_pptx(_two_slide_deck(), density=Density.PLAIN).text
        self.assertEqual(
            "\n".join(text.splitlines()[1:]),
            "=== Slide 1 ===\nTitle\n\nPoint one\nPoint two\n=== Slide 2 ===\nSecret",
        )

    def test_unknown_density_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "density"):
            parse_pptx(_two_slide_deck(), density="typo")  # type: ignore[arg-type]

    def test_structural_density_renders_slides(self) -> None:
        text = parse_pptx(_two_slide_deck(), density=Density.STRUCTURAL).text
        root = ET.fromstring(text)
        self.assertEqual(root.get("density"), "structural")
        slides = [(item.get("number"), item.get("hidden")) for item in root.findall("slide")]
        self.assertEqual(slides, [("1", None), ("2", "true")])

    def test_semantic_density_renders_slides(self) -> None:
        text = parse_pptx(_two_slide_deck(), density=Density.SEMANTIC).text
        root = ET.fromstring(text)
        self.assertEqual(root.get("density"), "semantic")

    def test_default_densities_preserve_source_shape_order(self) -> None:
        slide = slide_xml_shapes(
            text_shape_xml([[("t", "First in XML")]], shape_id=2, geometry=(0, 3000000, 1000000, 500000))
            + text_shape_xml([[("t", "Second in XML")]], shape_id=3, geometry=(0, 0, 1000000, 500000))
        )
        deck = make_pptx(
            {
                "[Content_Types].xml": content_types_xml(1),
                "_rels/.rels": root_rels_xml(),
                "ppt/presentation.xml": presentation_xml(1),
                "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
                "ppt/slides/slide1.xml": slide,
            }
        )
        expected = ["First in XML", "Second in XML"]
        plain = parse_pptx(deck, density=Density.PLAIN).text
        self.assertLess(plain.index(expected[0]), plain.index(expected[1]))
        for density in (Density.STRUCTURAL, Density.SEMANTIC):
            root = ET.fromstring(parse_pptx(deck, density=density).text)
            self.assertEqual(["".join(node.itertext()) for node in root.findall(".//p")], expected)
        with open_pptx(deck) as session:
            for density in (Density.PLAIN, Density.STRUCTURAL, Density.SEMANTIC):
                text = session.render(density=density).text
                self.assertLess(text.index(expected[0]), text.index(expected[1]))


if __name__ == "__main__":
    unittest.main()
