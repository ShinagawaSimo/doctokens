"""Regression coverage for fidelity and fail-soft PPTX paths."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _pptx_fixtures import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    rich_deck_pptx,
    rich_text_shape_xml,
    root_rels_xml,
    slide_xml_shapes,
    table_shape_xml,
    text_shape_xml,
)
from pptx_llm_parser import Density, get_resource, iter_slides, parse_pptx
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parser import PptxParser


def _deck(shapes: str, *, slide_xml: str | None = None, slide_rels: str | None = None) -> Path:
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(1),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml or slide_xml_shapes(shapes),
    }
    if slide_rels is not None:
        entries["ppt/slides/_rels/slide1.xml.rels"] = slide_rels
    return make_pptx(entries)


class ExtendedPptxTests(unittest.TestCase):
    def test_real_run_attributes_and_malformed_color_are_fail_soft(self) -> None:
        run = (
            '<a:r><a:rPr b="1" i="1" u="sng"><a:solidFill>'
            '<a:srgbClr val="FF0000"><a:tint val="bad"/></a:srgbClr>'
            "</a:solidFill></a:rPr><a:t>Styled</a:t></a:r>"
        )
        parsed = PptxParser().parse(_deck(rich_text_shape_xml([run])), ParseOptions())
        fmt = parsed.slides[0]["shapes"][0]["runs"][0]["format"]
        self.assertEqual((fmt["bold"], fmt["italic"], fmt["underline"]), (True, True, True))
        self.assertTrue(any(warning.code == "COLOR_VALUE_INVALID" for warning in parsed.warnings))

    def test_group_coordinates_are_mapped_to_slide_space(self) -> None:
        child = text_shape_xml([[("t", "Grouped")]], geometry=(10, 20, 30, 40))
        group = (
            "<p:grpSp><p:nvGrpSpPr/><p:grpSpPr><a:xfrm>"
            '<a:off x="100" y="200"/><a:ext cx="1000" cy="2000"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="100" cy="200"/>'
            f"</a:xfrm></p:grpSpPr>{child}</p:grpSp>"
        )
        shape = PptxParser().parse(_deck(group), ParseOptions()).slides[0]["shapes"][0]
        self.assertEqual(shape["text"], "Grouped")
        self.assertEqual(shape["x"], round(200 / 12192000 * 1000))
        self.assertEqual(shape["y"], round(400 / 6858000 * 1000))

    def test_lists_formula_background_and_merged_table_are_preserved(self) -> None:
        paragraphs = [
            '<a:pPr><a:buAutoNum type="arabicPeriod" startAt="3"/></a:pPr><a:r><a:t>One</a:t></a:r>',
            '<a:pPr><a:buAutoNum type="arabicPeriod" startAt="3"/></a:pPr><a:r><a:t>Two</a:t></a:r>',
            '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            "<m:f><m:num><m:r><m:t>a</m:t></m:r></m:num><m:den><m:r><m:t>b</m:t></m:r></m:den></m:f>"
            "</m:oMath>",
        ]
        table = table_shape_xml([["A", ""]])
        table = table.replace("<a:tc>", '<a:tc gridSpan="2">', 1)
        second = table.find("<a:tc>")
        table = table[:second] + '<a:tc hMerge="1">' + table[second + len("<a:tc>") :]
        slide = slide_xml_shapes(rich_text_shape_xml(paragraphs) + table)
        slide = slide.replace(
            "<p:cSld>",
            '<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="112233"/></a:solidFill></p:bgPr></p:bg>',
        )
        deck = _deck("", slide_xml=slide)
        parsed = PptxParser().parse(deck, ParseOptions())
        text_shape, table_shape = parsed.slides[0]["shapes"]
        self.assertEqual(text_shape["text"], "3. One\n4. Two\n\\frac{a}{b}")
        self.assertEqual(text_shape["paragraphs"][0]["startAt"], 3)
        self.assertEqual(parsed.slides[0]["background"], {"color": "#112233"})
        self.assertEqual(table_shape["tableCells"][0][0]["colSpan"], 2)
        rendered = parse_pptx(deck, density=Density.SEMANTIC)
        self.assertIn("<equation>\\frac{a}{b}</equation>", rendered)
        self.assertIn("<td colspan=2>A</td>", rendered)

    def test_markup_attributes_are_quoted_and_escaped(self) -> None:
        run = (
            '<a:r><a:rPr xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<a:hlinkClick r:id="rId2"/></a:rPr><a:t>link</a:t></a:r>'
        )
        rels = (
            '<?xml version="1.0"?><Relationships '
            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            'Target="https://example.test/a?x=one%20two&amp;y=&quot;q&quot;" TargetMode="External"/>'
            "</Relationships>"
        )
        rendered = parse_pptx(_deck(rich_text_shape_xml([run]), slide_rels=rels), density=Density.SEMANTIC)
        self.assertIn('href="https://example.test/a?x=one%20two&amp;y=&quot;q&quot;"', rendered)

    def test_stream_and_resources_do_not_call_full_parse(self) -> None:
        with patch.object(PptxParser, "parse", side_effect=AssertionError("full parse called")):
            self.assertTrue(list(iter_slides(rich_deck_pptx(), density=Density.PLAIN)))
            self.assertIsNotNone(get_resource(rich_deck_pptx(), "image", "img1"))
            self.assertIsNotNone(get_resource(rich_deck_pptx(), "chart", "chart1"))
            self.assertIsNotNone(get_resource(rich_deck_pptx(), "table", "table1"))

    def test_debug_artifacts_and_strict_numeric_options(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_zip_entries"):
            ParseOptions(max_zip_entries=True)
        with tempfile.TemporaryDirectory() as directory:
            parsed = PptxParser().parse(
                _deck(text_shape_xml([[("t", "Debug")]])),
                ParseOptions(debug=True, output_dir=Path(directory)),
            )
            self.assertIn("totalMs", parsed.metrics)
            self.assertTrue((Path(directory) / ".debug" / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
