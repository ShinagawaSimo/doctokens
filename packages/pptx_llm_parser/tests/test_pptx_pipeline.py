"""End-to-end plain rendering through the public API."""

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
from pptx_llm_parser import Density, parse_pptx


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
        text = parse_pptx(_two_slide_deck(), density=Density.PLAIN)
        self.assertTrue(text.startswith("density=plain\n"))

    def test_plain_separates_slides(self) -> None:
        text = parse_pptx(_two_slide_deck(), density=Density.PLAIN)
        self.assertIn("=== Slide 1 ===", text)
        self.assertIn("=== Slide 2 ===", text)

    def test_plain_includes_hidden_slide_text(self) -> None:
        text = parse_pptx(_two_slide_deck(), density=Density.PLAIN)
        self.assertIn("Secret", text)

    def test_plain_shape_layout(self) -> None:
        text = parse_pptx(_two_slide_deck(), density=Density.PLAIN)
        self.assertEqual(
            text,
            "density=plain\n=== Slide 1 ===\nTitle\n\nPoint one\nPoint two\n=== Slide 2 ===\nSecret",
        )

    def test_unknown_density_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "density"):
            parse_pptx(_two_slide_deck(), density="typo")  # type: ignore[arg-type]

    def test_unimplemented_densities_raise(self) -> None:
        for density in (Density.SEMANTIC, Density.STRUCTURAL):
            with self.assertRaisesRegex(NotImplementedError, "not implemented"):
                parse_pptx(_two_slide_deck(), density=density)


if __name__ == "__main__":
    unittest.main()
