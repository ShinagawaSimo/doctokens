"""Media shapes (p14:media) and lazy media asset indexing."""

from __future__ import annotations

import unittest

from _pptx_fixtures import (
    content_types_xml,
    make_pptx,
    media_shape_xml,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
)
from pptx_llm_parser import parse_pptx
from pptx_llm_parser.core.enums import Density
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parsing.runner import PptxParser


def _media_deck(kind: str = "video") -> bytes:
    rel = (
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/media" '
        'Target="../media/movie.mp4"/>'
    )
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(1, extra_defaults='<Default Extension="mp4" ContentType="video/mp4"/>'),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(media_shape_xml(kind=kind)),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(rel),
        "ppt/media/movie.mp4": b"",
    }
    return make_pptx(entries)


class MediaShapeTests(unittest.TestCase):
    def test_video_shape_and_asset(self) -> None:
        parsed = PptxParser().parse(_media_deck(), ParseOptions())
        shapes = parsed.slides[0]["shapes"]
        self.assertEqual(len(shapes), 1)
        self.assertEqual(shapes[0]["type"], "media")
        self.assertEqual(shapes[0]["kind"], "video")
        self.assertEqual(shapes[0]["assetId"], "media1")
        self.assertEqual(parsed.assets[0]["type"], "media")
        self.assertEqual(parsed.assets[0]["contentType"], "video/mp4")
        self.assertEqual(parsed.assets[0]["zipPath"], "ppt/media/movie.mp4")

    def test_audio_shape_kind(self) -> None:
        parsed = PptxParser().parse(_media_deck(kind="audio"), ParseOptions())
        self.assertEqual(parsed.slides[0]["shapes"][0]["kind"], "audio")

    def test_plain_video_placeholder(self) -> None:
        text = parse_pptx(_media_deck(), density=Density.PLAIN).text
        self.assertIn("[Video]", text)

    def test_plain_audio_placeholder(self) -> None:
        text = parse_pptx(_media_deck(kind="audio"), density=Density.PLAIN).text
        self.assertIn("[Audio]", text)


if __name__ == "__main__":
    unittest.main()
