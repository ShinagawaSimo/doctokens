"""Run-level format IR: bold/italic/underline, theme-resolved colors, hyperlinks."""

from __future__ import annotations

import unittest
from pathlib import Path

from _pptx_fixtures import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    rich_text_shape_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
    theme_xml,
)
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parser import PptxParser

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

_THEME_REL = (
    '<Relationship Id="rId99" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" '
    'Target="theme/theme1.xml"/>'
)
_THEME_OVERRIDE = (
    '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
)


def _runs_deck(shape_xml: str, *, slide_rels: str = "", with_theme: bool = True) -> Path:
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(1, extra_defaults=_THEME_OVERRIDE),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1, extra=_THEME_REL if with_theme else ""),
        "ppt/slides/slide1.xml": slide_xml_shapes(shape_xml),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(slide_rels),
    }
    if with_theme:
        entries["ppt/theme/theme1.xml"] = theme_xml()
    return make_pptx(entries)


def _shape_runs(deck: bytes) -> list[dict]:
    parsed = PptxParser().parse(deck, ParseOptions())
    return parsed.slides[0]["shapes"][0]["runs"]


class RunFormatTests(unittest.TestCase):
    def test_bold_run(self) -> None:
        deck = _runs_deck(rich_text_shape_xml([f'<a:r><a:rPr xmlns:a="{_A}"><a:b/></a:rPr><a:t>Hi</a:t></a:r>']))
        runs = _shape_runs(deck)
        self.assertEqual(runs[0]["text"], "Hi")
        self.assertEqual(runs[0]["format"], {"bold": True})

    def test_italic_and_underline(self) -> None:
        deck = _runs_deck(rich_text_shape_xml([f'<a:r><a:rPr xmlns:a="{_A}"><a:i/><a:u/></a:rPr><a:t>X</a:t></a:r>']))
        self.assertEqual(_shape_runs(deck)[0]["format"], {"italic": True, "underline": True})

    def test_srgb_color(self) -> None:
        deck = _runs_deck(
            rich_text_shape_xml(
                [f'<a:r><a:rPr xmlns:a="{_A}"><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill></a:rPr><a:t>C</a:t></a:r>']
            )
        )
        self.assertEqual(_shape_runs(deck)[0]["format"], {"color": "#FF0000"})

    def test_scheme_color_resolved_through_theme(self) -> None:
        deck = _runs_deck(
            rich_text_shape_xml(
                [f'<a:r><a:rPr xmlns:a="{_A}"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:rPr><a:t>C</a:t></a:r>']
            )
        )
        self.assertEqual(_shape_runs(deck)[0]["format"], {"color": "#4472C4"})

    def test_near_black_scheme_color_filtered(self) -> None:
        deck = _runs_deck(
            rich_text_shape_xml(
                [f'<a:r><a:rPr xmlns:a="{_A}"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill></a:rPr><a:t>C</a:t></a:r>']
            )
        )
        parsed = PptxParser().parse(deck, ParseOptions())
        shape = parsed.slides[0]["shapes"][0]
        self.assertEqual(shape["text"], "C")
        self.assertNotIn("runs", shape)

    def test_hyperlink_run(self) -> None:
        rel = (
            '<Relationship Id="rId40" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            'Target="https://example.test/doc" TargetMode="External"/>'
        )
        deck = _runs_deck(
            rich_text_shape_xml(
                [f'<a:r><a:rPr xmlns:a="{_A}" xmlns:r="{_R}"><a:hlinkClick r:id="rId40"/></a:rPr><a:t>Go</a:t></a:r>']
            ),
            slide_rels=rel,
        )
        self.assertEqual(_shape_runs(deck)[0]["link"], "https://example.test/doc")

    def test_plain_text_shape_omits_runs(self) -> None:
        deck = _runs_deck(rich_text_shape_xml(["<a:r><a:t>A</a:t></a:r><a:br/><a:tab/><a:r><a:t>B</a:t></a:r>"]))
        parsed = PptxParser().parse(deck, ParseOptions())
        shape = parsed.slides[0]["shapes"][0]
        self.assertEqual(shape["text"], "A\n\tB")
        self.assertNotIn("runs", shape)

    def test_paragraphs_join_in_text(self) -> None:
        deck = _runs_deck(rich_text_shape_xml(["<a:r><a:t>One</a:t></a:r>", "<a:r><a:t>Two</a:t></a:r>"]))
        parsed = PptxParser().parse(deck, ParseOptions())
        shape = parsed.slides[0]["shapes"][0]
        self.assertEqual(shape["text"], "One\nTwo")
        self.assertNotIn("runs", shape)

    def test_runs_match_flattened_text_when_formatted(self) -> None:
        deck = _runs_deck(
            rich_text_shape_xml([f'<a:r><a:t>A</a:t></a:r><a:br/><a:r><a:rPr xmlns:a="{_A}"><a:b/></a:rPr><a:t>B</a:t></a:r>'])
        )
        parsed = PptxParser().parse(deck, ParseOptions())
        shape = parsed.slides[0]["shapes"][0]
        self.assertEqual(shape["text"], "".join(run["text"] for run in shape["runs"]))
        self.assertEqual(shape["runs"][0], {"text": "A"})
        self.assertEqual(shape["runs"][2], {"text": "B", "format": {"bold": True}})


if __name__ == "__main__":
    unittest.main()
