"""Run-level format IR: bold/italic/underline, theme-resolved colors, hyperlinks."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

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
from pptx_llm_parser import parse_pptx

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"

_THEME_REL = (
    '<Relationship Id="rId99" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" '
    'Target="theme/theme1.xml"/>'
)
_THEME_OVERRIDE = (
    '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
)


def _runs_deck(shape_xml: str, *, slide_rels: str = "", with_theme: bool = True) -> bytes:
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


def _semantic(deck: bytes) -> ET.Element:
    return ET.fromstring(parse_pptx(deck, density="semantic").text)


class RunFormatTests(unittest.TestCase):
    def test_italic_and_underline(self) -> None:
        deck = _runs_deck(rich_text_shape_xml([f'<a:r><a:rPr xmlns:a="{_A}"><a:i/><a:u/></a:rPr><a:t>X</a:t></a:r>']))
        root = _semantic(deck)
        self.assertEqual("".join(root.find(".//i").itertext()), "X")
        self.assertIsNotNone(root.find(".//u"))

    def test_scheme_color_resolved_through_theme(self) -> None:
        deck = _runs_deck(
            rich_text_shape_xml(
                [f'<a:r><a:rPr xmlns:a="{_A}"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:rPr><a:t>C</a:t></a:r>']
            )
        )
        self.assertEqual(_semantic(deck).find(".//color").get("value"), "#4472C4")

    def test_near_black_scheme_color_filtered(self) -> None:
        deck = _runs_deck(
            rich_text_shape_xml(
                [f'<a:r><a:rPr xmlns:a="{_A}"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill></a:rPr><a:t>C</a:t></a:r>']
            )
        )
        self.assertIsNone(_semantic(deck).find(".//color"))


if __name__ == "__main__":
    unittest.main()
