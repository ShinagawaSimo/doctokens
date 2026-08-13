"""Speaker notes: notesSlide extraction and plain rendering."""

from __future__ import annotations

import unittest

from _pptx_fixtures import (
    content_types_xml,
    make_pptx,
    notes_slide_xml,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
    text_shape_xml,
)
from pptx_llm_parser import Density, parse_pptx
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parser import PptxParser

_NOTES_REL = (
    '<Relationship Id="rId20" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" '
    'Target="../notesSlides/notesSlide1.xml"/>'
)
_NOTES_OVERRIDE = (
    '<Override PartName="/ppt/notesSlides/notesSlide1.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>'
)


def _notes_deck(*, with_notes: bool = True, with_part: bool = True) -> bytes:
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(1, extra_defaults=_NOTES_OVERRIDE),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(text_shape_xml([[("t", "Slide text")]])),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(_NOTES_REL if with_notes else ""),
    }
    if with_notes and with_part:
        entries["ppt/notesSlides/notesSlide1.xml"] = notes_slide_xml([[("t", "Talk about this")], [("t", "And that")]])
    return make_pptx(entries)


class NotesTests(unittest.TestCase):
    def test_notes_text_extracted(self) -> None:
        parsed = PptxParser().parse(_notes_deck(), ParseOptions())
        self.assertEqual(parsed.slides[0]["notes"], "Talk about this\nAnd that")

    def test_slide_without_notes_rel_has_none(self) -> None:
        parsed = PptxParser().parse(_notes_deck(with_notes=False), ParseOptions())
        self.assertIsNone(parsed.slides[0]["notes"])

    def test_missing_notes_part_degrades_with_warning(self) -> None:
        parsed = PptxParser().parse(_notes_deck(with_part=False), ParseOptions())
        self.assertIsNone(parsed.slides[0]["notes"])
        self.assertTrue(any(w.code == "NOTES_PART_MISSING" for w in parsed.warnings))

    def test_plain_renders_notes_after_slide_text(self) -> None:
        text = parse_pptx(_notes_deck(), density=Density.PLAIN)
        self.assertIn("Slide text\n\n[Notes: Talk about this\nAnd that]", text)

    def test_plain_without_notes_omits_section(self) -> None:
        text = parse_pptx(_notes_deck(with_notes=False), density=Density.PLAIN)
        self.assertNotIn("[Notes:", text)


if __name__ == "__main__":
    unittest.main()
