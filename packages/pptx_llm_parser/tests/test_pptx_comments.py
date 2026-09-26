"""Modern threaded comments (p15): authors, threads, plain rendering."""

from __future__ import annotations

import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from _pptx_fixtures import (
    comment_authors_xml,
    comments_xml,
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
    text_shape_xml,
)
from pptx_llm_parser import open_pptx, parse_pptx
from pptx_llm_parser import parse_pptx as parse_pptx_result
from pptx_llm_parser.core.enums import Density
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parsing.runner import PptxParser

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


def _comments_deck(
    *,
    with_comments: bool = True,
    with_authors: bool = True,
    comments_content: str | None = None,
) -> bytes:
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(1, extra_defaults=_OVERRIDES),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1, extra=_COMMENTS_REL),
        "ppt/slides/slide1.xml": slide_xml_shapes(text_shape_xml([[("t", "Slide")]])),
    }
    if with_comments:
        entries["ppt/comments/comment1.xml"] = comments_content or comments_xml()
    if with_authors:
        entries["ppt/commentAuthors.xml"] = comment_authors_xml()
    return make_pptx(entries)


def _classic_comments_deck() -> bytes:
    presentation_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
    comment_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(2),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(2),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(2),
    }
    for number, escaped_text in ((1, " First &amp; &lt;one&gt; "), (2, "Second")):
        entries[f"ppt/slides/slide{number}.xml"] = slide_xml_shapes(text_shape_xml([[("t", f"Slide {number}")]]))
        entries[f"ppt/slides/_rels/slide{number}.xml.rels"] = slide_rels_xml(
            f'<Relationship Id="rComment" Type="{comment_rel}" Target="../comments/comment{number}.xml"/>'
        )
        entries[f"ppt/comments/comment{number}.xml"] = (
            f'<p:cmLst xmlns:p="{presentation_ns}">'
            f'<p:cm authorId="0" idx="{number}"><p:pos x="0" y="0"/>'
            f"<p:text>{escaped_text}</p:text></p:cm></p:cmLst>"
        )
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
        self.assertEqual(second["parentCommentId"], "cmt1")

    def test_parent_id_maps_by_raw_comment_idx(self) -> None:
        content = comments_xml().replace('idx="1"', 'idx="7"').replace('parentId="1"', 'parentId="7"')
        parsed = PptxParser().parse(_comments_deck(comments_content=content), ParseOptions())
        self.assertEqual(parsed.comments[1]["parentId"], "7")
        self.assertEqual(parsed.comments[1]["parentCommentId"], "cmt1")

    def test_missing_comments_part_yields_warning_and_no_comments(self) -> None:
        parsed = PptxParser().parse(_comments_deck(with_comments=False), ParseOptions())
        self.assertEqual(parsed.comments, [])
        self.assertTrue(any(w.code == "COMMENTS_PART_MISSING" for w in parsed.warnings))

    def test_missing_authors_degrades_to_empty_author(self) -> None:
        parsed = PptxParser().parse(_comments_deck(with_authors=False), ParseOptions())
        self.assertEqual(parsed.comments[0]["author"], "")

    def test_plain_appends_comments_section(self) -> None:
        text = parse_pptx(_comments_deck(), density=Density.PLAIN).text
        self.assertIn("[Comments]", text)
        self.assertIn("[cmt1: Nice slide]", text)
        self.assertIn("[cmt2: Agreed]", text)

    def test_plain_without_comments_omits_section(self) -> None:
        text = parse_pptx(_comments_deck(with_comments=False), density=Density.PLAIN).text
        self.assertNotIn("[Comments]", text)

    def test_classic_comment_text_and_slide_ownership(self) -> None:
        source = _classic_comments_deck()
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "comments.pptx"
        path.write_bytes(source)
        expected = [("slide1", " First & <one> "), ("slide2", "Second")]
        for input_source in (path, source):
            result = parse_pptx_result(input_source, density="semantic")
            comments = ET.fromstring(result.text).findall("./comments/comment")
            self.assertEqual([(node.get("slide"), node.text) for node in comments], expected)
            self.assertEqual(sum(w.code == "LEGACY_COMMENTS_PARSED" for w in result.report.warnings), 2)
            first_slide = parse_pptx_result(input_source, density="semantic", slide=1)
            selected = ET.fromstring(first_slide.text).findall("./comments/comment")
            self.assertEqual([(node.get("slide"), node.text) for node in selected], expected[:1])
            plain = parse_pptx_result(input_source, density="plain")
            self.assertIn("[cmt1:  First & <one> ]", plain.text)
        with open_pptx(source) as session:
            result = session.render(density="semantic")
            comments = ET.fromstring(result.text).findall("./comments/comment")
            self.assertEqual([(node.get("slide"), node.text) for node in comments], expected)
            second_slide = session.render(density="semantic", slide=2)
            selected = ET.fromstring(second_slide.text).findall("./comments/comment")
            self.assertEqual([(node.get("slide"), node.text) for node in selected], expected[1:])

    def test_classic_empty_text_and_modern_text_are_distinct(self) -> None:
        source = _classic_comments_deck()
        with zipfile.ZipFile(BytesIO(source)) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        entries["ppt/comments/comment1.xml"] = entries["ppt/comments/comment1.xml"].replace(b" First &amp; &lt;one&gt; ", b"")
        empty = make_pptx(entries)
        parsed = PptxParser().parse(empty, ParseOptions())
        self.assertEqual(parsed.comments[0]["text"], "")
        self.assertEqual(parsed.comments[1]["text"], "Second")
        modern = PptxParser().parse(_comments_deck(), ParseOptions())
        self.assertEqual([item["text"] for item in modern.comments], ["Nice slide", "Agreed"])


if __name__ == "__main__":
    unittest.main()
