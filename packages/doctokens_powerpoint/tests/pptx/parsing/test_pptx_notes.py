"""Damaged speaker-note relationships and bodies cannot be produced by normal Office UI."""

from __future__ import annotations

import pytest
from _pptx_package import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
)
from doctokens_powerpoint import open_pptx, parse_pptx

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (None, "NOTES_PART_MISSING"),
        ("<broken", "NOTES_XML_INVALID"),
        (f'<p:notes xmlns:p="{_P}"><p:cSld/></p:notes>', "NOTES_MISSING_SPTREE"),
    ],
)
def test_unreadable_note_part_retains_a_placeholder(body: str | None, code: str) -> None:
    # Each case deliberately corrupts an otherwise present notes relationship.
    entries = {
        "[Content_Types].xml": content_types_xml(1),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(""),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(
            '<Relationship Id="n" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" '
            'Target="../notesSlides/notes1.xml"/>'
        ),
    }
    if body is not None:
        entries["ppt/notesSlides/notes1.xml"] = body
    source = make_pptx(entries)
    for density in ("plain", "structural", "semantic"):
        result = parse_pptx(source, density=density)
        assert code in [item.code for item in result.report.warnings]
        expected = (
            "density=plain format=pptx\n=== Slide 1 ===\n[Notes: [Unparsed speaker notes]]"
            if density == "plain"
            else f'<presentation density="{density}" format="pptx"><slide number="1">'
            "<speaker-notes>[Unparsed speaker notes]</speaker-notes></slide></presentation>"
        )
        assert result.text == expected
    with open_pptx(source) as session:
        assert not session.find_text("Unparsed").matches
