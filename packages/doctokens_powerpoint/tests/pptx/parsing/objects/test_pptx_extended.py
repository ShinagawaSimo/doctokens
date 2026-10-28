"""Regression coverage for fidelity and fail-soft PPTX paths."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from _pptx_decks import rich_deck_pptx
from _pptx_objects import table_shape_xml
from _pptx_package import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    rich_text_shape_xml,
    root_rels_xml,
    slide_xml_shapes,
)
from doctokens_powerpoint import open_pptx, parse_pptx
from doctokens_powerpoint.pptx.model.enums import Density
from doctokens_powerpoint.pptx.model.presentation import ParseOptions
from doctokens_powerpoint.pptx.parsing.runner import PptxParser


def _deck(shapes: str, *, slide_xml: str | None = None, slide_rels: str | None = None) -> bytes:
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
        self.assertTrue(any(warning.code == "COLOR_VALUE_INVALID" for warning in parsed.warnings))

    def test_lists_formula_background_and_merged_table_are_preserved(self) -> None:
        paragraphs = [
            '<a:pPr><a:buAutoNum type="arabicPeriod" startAt="3"/></a:pPr><a:r><a:t>One</a:t></a:r>',
            '<a:pPr><a:buAutoNum type="arabicPeriod" startAt="3"/></a:pPr><a:r><a:t>Two</a:t></a:r>',
            '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            'xmlns:math2010="http://schemas.microsoft.com/office/drawing/2010/main">'
            '<mc:Choice Requires="math2010"><math2010:m>'
            '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            "<m:f><m:num><m:r><m:t>a</m:t></m:r></m:num><m:den><m:r><m:t>b</m:t></m:r></m:den></m:f>"
            "</m:oMath></math2010:m></mc:Choice><mc:Fallback><a:r><a:t>Old preview</a:t></a:r></mc:Fallback>"
            "</mc:AlternateContent>",
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
        rendered = parse_pptx(deck, density=Density.SEMANTIC).text
        root = ET.fromstring(rendered)
        self.assertEqual(root.findtext(".//equation"), "\\frac{a}{b}")
        self.assertEqual(root.find(".//table/tr/td").get("colspan"), "2")

    def test_math_requires_unbound_unknown_and_rebound_prefixes(self) -> None:
        # Namespace errors and unsupported producer extensions are exceptional;
        # ordinary math will migrate to the pending native pptx-equation file.
        expression = (
            '<native:m><m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            "<m:r><m:t>x</m:t></m:r></m:oMath></native:m>"
        )
        for requires, declarations in (
            ("missing", ""),
            ("math2010 future", 'xmlns:future="urn:unsupported"'),
            ("math2010", 'xmlns:math2010="urn:rebound"'),
        ):
            with self.subTest(requires=requires, declarations=declarations):
                paragraph = (
                    '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
                    'xmlns:math2010="http://schemas.microsoft.com/office/drawing/2010/main" '
                    'xmlns:native="http://schemas.microsoft.com/office/drawing/2010/main">'
                    f'<mc:Choice Requires="{requires}" {declarations}>{expression}</mc:Choice>'
                    "<mc:Fallback><a:r><a:t>Saved fallback</a:t></a:r></mc:Fallback></mc:AlternateContent>"
                )
                rendered = ET.fromstring(parse_pptx(_deck(rich_text_shape_xml([paragraph])), density="semantic").text)
                self.assertEqual(rendered.findtext(".//slide/p"), "Saved fallback")
                self.assertIsNone(rendered.find(".//equation"))

    def test_math_without_a_supported_branch_reports_incomplete_content(self) -> None:
        # A missing fallback after an unbound requirement is not normal Office content.
        paragraph = (
            '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            'xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main">'
            '<mc:Choice Requires="missing"><a14:m>'
            '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            "<m:r><m:t>x</m:t></m:r></m:oMath></a14:m></mc:Choice></mc:AlternateContent>"
        )
        result = parse_pptx(_deck(rich_text_shape_xml([paragraph])), density="plain")
        self.assertEqual(
            [warning.code for warning in result.report.warnings if warning.code.startswith("MATH_")],
            ["MATH_ALTERNATE_CONTENT_UNSUPPORTED"],
        )

    def test_nested_math_alternatives_read_one_native_representation(self) -> None:
        # Temporary native-math migration case; no Office fixture exists yet.
        paragraph = (
            '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            'xmlns:math="http://schemas.microsoft.com/office/drawing/2010/main">'
            '<mc:Choice Requires="math"><mc:AlternateContent><mc:Choice Requires="math"><math:m>'
            '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            "<m:r><m:t>x</m:t></m:r></m:oMath></math:m></mc:Choice>"
            "<mc:Fallback><a:r><a:t>Inner preview</a:t></a:r></mc:Fallback></mc:AlternateContent></mc:Choice>"
            "<mc:Fallback><a:r><a:t>Outer preview</a:t></a:r></mc:Fallback></mc:AlternateContent>"
        )
        source = _deck(rich_text_shape_xml([paragraph]))
        for density in ("plain", "structural", "semantic"):
            with self.subTest(density=density):
                if density == "plain":
                    expected = "density=plain format=pptx\n=== Slide 1 ===\nx"
                else:
                    name = ' name="Rich 9"' if density == "semantic" else ""
                    expected = (
                        f'<presentation density="{density}" format="pptx"><slide number="1">'
                        f'<p{name} shape-id="s1"><equation notation="latex">x</equation></p></slide></presentation>'
                    )
                self.assertEqual(parse_pptx(source, density=density).text, expected)
                with open_pptx(source) as session:
                    self.assertEqual(session.render(density=density).text, expected)

    def test_drawingml_autonumber_schemes_use_shared_formatters(self) -> None:
        paragraphs = [
            '<a:pPr><a:buAutoNum type="alphaUcParenBoth" startAt="3"/></a:pPr><a:r><a:t>Alpha</a:t></a:r>',
            '<a:pPr><a:buAutoNum type="romanLcParenR" startAt="3"/></a:pPr><a:r><a:t>Roman</a:t></a:r>',
            '<a:pPr><a:buAutoNum type="arabicDbPeriod" startAt="3"/></a:pPr><a:r><a:t>Full width</a:t></a:r>',
        ]
        text = parse_pptx(_deck(rich_text_shape_xml(paragraphs)), density="plain").text
        self.assertIn("(C) Alpha\niii) Roman\n３． Full width", text)

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
        rendered = parse_pptx(_deck(rich_text_shape_xml([run]), slide_rels=rels), density=Density.SEMANTIC).text
        self.assertIn('href="https://example.test/a?x=one%20two&amp;y=&quot;q&quot;"', rendered)

    def test_output_iteration_parses_once_and_resources_use_lightweight_lookup(self) -> None:
        with patch.object(PptxParser, "parse", wraps=PptxParser().parse) as parse_mock:
            with open_pptx(rich_deck_pptx()) as session:
                self.assertTrue(list(session.iter_render(density=Density.PLAIN)))
            parse_mock.assert_called_once()
        with open_pptx(rich_deck_pptx()) as session:
            self.assertTrue(session.read_resource("image", "img1"))
            self.assertIn("<chart", session.render_resource("chart", "chart1").text)
            self.assertIn("<table", session.render_resource("table", "table1").text)

    def test_strict_numeric_options(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_zip_entries"):
            ParseOptions(max_zip_entries=True)


if __name__ == "__main__":
    unittest.main()
