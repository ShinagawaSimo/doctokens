"""presentation.xml parsing: slide order, ids, size, hidden flags, fail-soft warnings."""

from __future__ import annotations

import unittest
from pathlib import Path

from _pptx_fixtures import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_xml,
)
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parser import PptxParser


def _deck(slide_count: int = 2, *, hidden: set[int] | None = None, drop_slide_parts: bool = False) -> Path:
    entries = {
        "[Content_Types].xml": content_types_xml(slide_count),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(slide_count),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(slide_count),
    }
    hidden = hidden or set()
    for i in range(slide_count):
        if drop_slide_parts:
            continue
        entries[f"ppt/slides/slide{i + 1}.xml"] = slide_xml(hidden=i + 1 in hidden)
    return make_pptx(entries)


class PresentationParsingTests(unittest.TestCase):
    def test_slide_order_parts_and_ids_follow_sld_id_lst(self) -> None:
        parsed = PptxParser().parse(_deck(2), ParseOptions())
        self.assertEqual([slide["n"] for slide in parsed.slides], [1, 2])
        self.assertEqual(
            [slide["part"] for slide in parsed.slides],
            ["ppt/slides/slide1.xml", "ppt/slides/slide2.xml"],
        )
        self.assertEqual([slide["sldId"] for slide in parsed.slides], ["256", "257"])
        self.assertTrue(all(slide["type"] == "slide" for slide in parsed.slides))

    def test_slide_size(self) -> None:
        parsed = PptxParser().parse(_deck(2), ParseOptions())
        self.assertEqual(parsed.slide_size, (12192000, 6858000))

    def test_hidden_slide_flag(self) -> None:
        parsed = PptxParser().parse(_deck(2, hidden={2}), ParseOptions())
        self.assertFalse(parsed.slides[0]["hidden"])
        self.assertTrue(parsed.slides[1]["hidden"])

    def test_missing_sld_id_lst_yields_warning_and_no_slides(self) -> None:
        entries = {
            "[Content_Types].xml": content_types_xml(),
            "_rels/.rels": root_rels_xml(),
            "ppt/presentation.xml": presentation_xml(slide_count=0),
            "ppt/_rels/presentation.xml.rels": presentation_rels_xml(0),
        }
        parsed = PptxParser().parse(make_pptx(entries), ParseOptions())
        self.assertEqual(parsed.slides, [])
        self.assertTrue(any(w.code == "PRESENTATION_MISSING_SLDIDLST" for w in parsed.warnings))

    def test_missing_slide_part_skips_with_warning(self) -> None:
        parsed = PptxParser().parse(_deck(2, drop_slide_parts=True), ParseOptions())
        self.assertEqual(parsed.slides, [])
        self.assertTrue(any(w.code == "SLIDE_PART_MISSING" for w in parsed.warnings))

    def test_slide_ref_without_rid_skips_with_warning(self) -> None:
        entries = {
            "[Content_Types].xml": content_types_xml(1),
            "_rels/.rels": root_rels_xml(),
            "ppt/presentation.xml": (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                '<p:sldIdLst><p:sldId id="256"/></p:sldIdLst></p:presentation>'
            ),
            "ppt/_rels/presentation.xml.rels": presentation_rels_xml(0),
        }
        parsed = PptxParser().parse(make_pptx(entries), ParseOptions())
        self.assertEqual(parsed.slides, [])
        self.assertTrue(any(w.code == "SLIDE_MISSING_RID" for w in parsed.warnings))


if __name__ == "__main__":
    unittest.main()
