"""Modern threaded comments (p15): authors, threads, plain rendering."""

from __future__ import annotations

import unittest

from _pptx_fixtures import (
    comment_authors_xml,
    comments_xml,
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_xml_shapes,
    text_shape_xml,
)
from pptx_llm_parser import Density, parse_pptx
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parser import PptxParser

_COMMENTS_REL = (
    '<Relationship Id="rId30" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" '
    'Target="comments/comment1.xml"/>'
    '<Relationship Id="rId31" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors" '
    'Target="commentAuthors.xml"/>'
)
_OVERRIDES = (
    '<Override PartName="/ppt/comments/comment1.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.presentationml.comments+xml"/>'
    '<Override PartName="/ppt/commentAuthors.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.presentationml.commentAuthors+xml"/>'
)


def _comments_deck(*, with_comments: bool = True, with_authors: bool = True) -> bytes:
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(1, extra_defaults=_OVERRIDES),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1, extra=_COMMENTS_REL),
        "ppt/slides/slide1.xml": slide_xml_shapes(text_shape_xml([[("t", "Slide")]])),
    }
    if with_comments:
        entries["ppt/comments/comment1.xml"] = comments_xml()
    if with_authors:
        entries["ppt/commentAuthors.xml"] = comment_authors_xml()
    return make_pptx(entries)


class CommentsTests(unittest.TestCase):
    def test_comments_with_authors_and_thread(self) -> None:
        parsed = PptxParser().parse(_comments_deck(), ParseOptions())
        self.assertEqual(len(parsed.comments), 2)
        first = parsed.comments[0]
        self.assertEqual(first["id"], "cmt1")
        self.assertEqual(first["text"], "Nice slide")
        self.assertEqual(first["author"], "Alice")
        self.assertEqual(first["date"], "2026-08-13T10:00:00")
        second = parsed.comments[1]
        self.assertEqual(second["id"], "cmt2")
        self.assertEqual(second["author"], "Bob")
        self.assertEqual(second["parentId"], "1")

    def test_missing_comments_part_yields_warning_and_no_comments(self) -> None:
        parsed = PptxParser().parse(_comments_deck(with_comments=False), ParseOptions())
        self.assertEqual(parsed.comments, [])
        self.assertTrue(any(w.code == "COMMENTS_PART_MISSING" for w in parsed.warnings))

    def test_missing_authors_degrades_to_empty_author(self) -> None:
        parsed = PptxParser().parse(_comments_deck(with_authors=False), ParseOptions())
        self.assertEqual(parsed.comments[0]["author"], "")

    def test_plain_appends_comments_section(self) -> None:
        text = parse_pptx(_comments_deck(), density=Density.PLAIN)
        self.assertIn("[Comments]", text)
        self.assertIn("[cmt1: Nice slide]", text)
        self.assertIn("[cmt2: Agreed]", text)

    def test_plain_without_comments_omits_section(self) -> None:
        text = parse_pptx(_comments_deck(with_comments=False), density=Density.PLAIN)
        self.assertNotIn("[Comments]", text)


if __name__ == "__main__":
    unittest.main()
