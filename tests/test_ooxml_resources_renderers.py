"""Focused tests for OOXML helpers, resources, and renderer branches."""

from __future__ import annotations

import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from docx_llm_parser.core.models import ContentTypes, ParseWarning, RelationshipRecord
from docx_llm_parser.core.relationships import RelationshipIndex
from docx_llm_parser.extractors.assets import IMAGE_REL_TYPE, AssetExtractor
from docx_llm_parser.ooxml.formatting import (
    is_default_text_color,
    merge_run_formats,
    normalize_hex_color,
    parse_run_format,
    visible_run_format,
)
from docx_llm_parser.ooxml.numbering import (
    NumberingInstance,
    NumberingLevel,
    NumberingMap,
    NumberingState,
)
from docx_llm_parser.ooxml.omml_latex import omath_to_latex
from docx_llm_parser.renderers.objects.charts import chart_to_html5, extract_chart_item
from docx_llm_parser.renderers.objects.smartarts import (
    extract_smartart_item,
    smartart_to_html5,
)
from docx_llm_parser.renderers.tables.render import render_table, table_id

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


class OoxmlFormattingAndMathTests(unittest.TestCase):
    def test_run_format_parses_visible_values_and_filters_defaults(self) -> None:
        run_properties = ET.fromstring(
            f"""<w:rPr xmlns:w="{W_NS}">
              <w:b/><w:i w:val="0"/><w:u w:val="single"/><w:dstrike/>
              <w:vertAlign w:val="subscript"/><w:color w:val="44AA44"/>
              <w:highlight w:val="none"/><w:shd w:fill="ABCDEF"/>
            </w:rPr>"""
        )

        parsed = parse_run_format(run_properties)

        self.assertEqual(
            parsed,
            {
                "bold": True,
                "italic": False,
                "underline": True,
                "strike": True,
                "subscript": True,
                "color": "#44AA44",
                "highlight": None,
                "bg": "#ABCDEF",
            },
        )
        merged = merge_run_formats({"bold": True, "color": "#FF0000"}, parsed)
        self.assertNotIn("italic", visible_run_format(merged))
        self.assertEqual(normalize_hex_color("00aa00"), "#00AA00")
        self.assertIsNone(normalize_hex_color("auto"))
        self.assertTrue(is_default_text_color("#101010"))
        self.assertFalse(is_default_text_color("themeAccent1"))

    def test_omml_converter_covers_structural_math_nodes(self) -> None:
        math = ET.fromstring(
            f"""<m:oMath xmlns:m="{M_NS}">
              <m:f><m:num><m:r><m:t>a&amp;b</m:t></m:r></m:num>
                <m:den><m:r><m:t>c_d</m:t></m:r></m:den></m:f>
              <m:rad><m:deg><m:r><m:t>3</m:t></m:r></m:deg>
                <m:e><m:r><m:t>x</m:t></m:r></m:e></m:rad>
              <m:sSub><m:e><m:r><m:t>x</m:t></m:r></m:e>
                <m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub>
              <m:sSup><m:e><m:r><m:t>y</m:t></m:r></m:e>
                <m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>
              <m:sSubSup><m:e><m:r><m:t>z</m:t></m:r></m:e>
                <m:sub><m:r><m:t>0</m:t></m:r></m:sub>
                <m:sup><m:r><m:t>n</m:t></m:r></m:sup></m:sSubSup>
              <m:sPre><m:e><m:r><m:t>A</m:t></m:r></m:e>
                <m:sub><m:r><m:t>l</m:t></m:r></m:sub>
                <m:sup><m:r><m:t>u</m:t></m:r></m:sup></m:sPre>
              <m:nary><m:chr m:val="∫"/><m:sub><m:r><m:t>0</m:t></m:r></m:sub>
                <m:sup><m:r><m:t>1</m:t></m:r></m:sup><m:e><m:r><m:t>f</m:t></m:r></m:e>
              </m:nary>
              <m:acc><m:chr m:val="⃗"/><m:e><m:r><m:t>v</m:t></m:r></m:e></m:acc>
              <m:bar><m:pr m:pos="bot"/><m:e><m:r><m:t>q</m:t></m:r></m:e></m:bar>
              <m:func><m:fName><m:r><m:t>lim</m:t></m:r></m:fName>
                <m:lim><m:r><m:t>x</m:t></m:r></m:lim><m:e><m:r><m:t>g</m:t></m:r></m:e>
              </m:func>
              <m:groupChr><m:pr m:chr="⏞"/><m:e><m:r><m:t>sum</m:t></m:r></m:e></m:groupChr>
              <m:d><m:pr m:begChr="[" m:endChr="]"/><m:e><m:r><m:t>p</m:t></m:r></m:e></m:d>
              <m:m><m:mr><m:e><m:r><m:t>1</m:t></m:r></m:e>
                <m:e><m:r><m:t>2</m:t></m:r></m:e></m:mr></m:m>
              <m:eqArr><m:e><m:r><m:t>x=1</m:t></m:r></m:e>
                <m:e><m:r><m:t>y=2</m:t></m:r></m:e></m:eqArr>
              <m:limLow><m:e><m:r><m:t>h</m:t></m:r></m:e>
                <m:lim><m:r><m:t>0</m:t></m:r></m:lim></m:limLow>
              <m:limUpp><m:e><m:r><m:t>h</m:t></m:r></m:e>
                <m:lim><m:r><m:t>∞</m:t></m:r></m:lim></m:limUpp>
              <m:phant><m:e><m:r><m:t>ghost</m:t></m:r></m:e></m:phant>
              <m:borderBox><m:e><m:r><m:t>box</m:t></m:r></m:e></m:borderBox>
              <m:box><m:e><m:r><m:t>pass</m:t></m:r></m:e></m:box>
              <m:unknown><m:r><m:t>plain</m:t></m:r></m:unknown>
            </m:oMath>"""
        )

        latex = omath_to_latex(math)

        self.assertIn(r"\frac{a\&b}{c\_d}", latex)
        self.assertIn(r"\sqrt[3]{x}", latex)
        self.assertIn(r"x_{i}", latex)
        self.assertIn(r"y^{2}", latex)
        self.assertIn(r"\int_{0}^{1} {f}", latex)
        self.assertIn(r"\vec{v}", latex)
        self.assertIn(r"\underline{q}", latex)
        self.assertIn(r"\lim_{x}{g}", latex)
        self.assertIn(r"\begin{matrix} 1 & 2 \end{matrix}", latex)
        self.assertIn(r"\boxed{box}", latex)


class NumberingAndAssetTests(unittest.TestCase):
    def test_numbering_state_formats_common_numbering_systems(self) -> None:
        formats = [
            ("decimalZero", 7, "07"),
            ("upperLetter", 27, "AA"),
            ("lowerLetter", 28, "ab"),
            ("upperRoman", 9, "IX"),
            ("lowerRoman", 4, "iv"),
            ("chineseCounting", 21, "二十一"),
            ("bullet", 1, "•"),
            ("unsupportedFormat", 3, "3"),
        ]
        levels = {
            index: NumberingLevel(
                numbering_level=index,
                start=start,
                number_format=number_format,
                suffix="nothing" if index % 2 == 0 else "space",
            )
            for index, (number_format, start, _expected) in enumerate(formats)
        }
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {"abstract": levels},
            {"7": NumberingInstance("7", "abstract")},
            warnings,
        )
        state = NumberingState(numbering, warnings)

        labels = [state.advance("7", index)["label"] for index in range(len(formats))]

        self.assertEqual(labels, [expected for _fmt, _start, expected in formats])
        self.assertEqual(warnings[0].code, "UNSUPPORTED_NUMBER_FORMAT")
        self.assertIsNone(state.advance("missing", 0, part="word/document.xml", block_id="b1"))
        self.assertEqual(warnings[-1].code, "NUMBERING_LEVEL_MISSING")

    def test_asset_extractor_handles_external_missing_embedded_and_compress_failure(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            warnings: list[ParseWarning] = []
            package = FakePackage(
                {
                    "word/media/image1.png": b"png-data",
                    "word/media/huge.bin": b"not an image" * 120_000,
                }
            )
            relationships = RelationshipIndex.from_records(
                [
                    RelationshipRecord(
                        "word/document.xml",
                        "rExt",
                        IMAGE_REL_TYPE,
                        "https://example.test/image.png",
                        "External",
                        "https://example.test/image.png",
                    ),
                    RelationshipRecord(
                        "word/document.xml",
                        "rMissing",
                        IMAGE_REL_TYPE,
                        "media/missing.png",
                        None,
                        "word/media/missing.png",
                    ),
                    RelationshipRecord(
                        "word/document.xml",
                        "rPng",
                        IMAGE_REL_TYPE,
                        "media/image1.png",
                        None,
                        "word/media/image1.png",
                    ),
                    RelationshipRecord(
                        "word/document.xml",
                        "rHuge",
                        IMAGE_REL_TYPE,
                        "media/huge.bin",
                        None,
                        "word/media/huge.bin",
                    ),
                ]
            )
            content_types: ContentTypes = {
                "defaults": {"bin": "application/octet-stream"},
                "overrides": {"word/media/image1.png": "image/png"},
            }

            assets, lookup = AssetExtractor(
                package,
                relationships,
                content_types,
                output_dir,
                warnings,
            ).extract()

            self.assertEqual(
                [asset["source"] for asset in assets],
                ["external", "embedded", "embedded"],
            )
            self.assertEqual(assets[1]["contentType"], "image/png")
            self.assertEqual(assets[2]["contentType"], "application/octet-stream")
            self.assertEqual(lookup[("word/document.xml", "rPng")]["id"], assets[1]["id"])
            self.assertIn("IMAGE_TARGET_MISSING", [warning.code for warning in warnings])
            self.assertIn("IMAGE_COMPRESS_FAILED", [warning.code for warning in warnings])


class RendererBranchTests(unittest.TestCase):
    def test_chart_smartart_and_table_renderers_cover_truncation_and_variants(self) -> None:
        series = [
            {
                "index": index,
                "pointCount": 2,
                "preview": f"Q{index}=1; Q{index + 1}=2",
                "name": f"S{index}",
                "min": 1.0,
                "max": float(index + 2),
            }
            for index in range(1, 7)
        ]
        chart = {
            "id": "chartX",
            "type": "chart",
            "chartType": "bar",
            "part": "word/charts/chart1.xml",
            "seriesCount": len(series),
            "pointCount": 12,
            "series": series,
            "title": "Sales",
        }

        self.assertIn("<ms c=2/>", chart_to_html5(chart))
        self.assertIn("names=Q1,Q2", chart_to_html5({**chart, "chartType": "pie"}))
        self.assertIn("points=12", chart_to_html5({**chart, "chartType": "scatter"}))
        self.assertIn("x=Q1,Q2", chart_to_html5({**chart, "chartType": "stock"}))
        self.assertIn("names=S1,S2", chart_to_html5({**chart, "chartType": "surface"}))
        self.assertIn('Use extract("chart", "empty")', chart_to_html5({"id": "empty"}))
        self.assertEqual(extract_chart_item(chart)["series"][0]["points"], ["Q1=1", "Q2=2"])

        smartart = {
            "id": "sa1",
            "type": "smartart",
            "part": "word/diagrams/data1.xml",
            "nodeCount": 14,
            "linkCount": 18,
            "rawLinkCount": 18,
            "layoutType": "process",
            "nodes": [
                {"modelId": f"n{index}", "text": f"Node {index}", "kind": "node"}
                for index in range(1, 15)
            ],
            "links": [{"from": index, "to": index + 1, "kind": "parOf"} for index in range(1, 19)],
        }

        rendered_sa = smartart_to_html5(smartart)
        self.assertIn("<mn c=2/>", rendered_sa)
        self.assertIn("<ml c=2/>", rendered_sa)
        self.assertIn("Node 1", extract_smartart_item(smartart)["nodes"][0]["text"])
        self.assertIn('Use extract("smartart", "empty")', smartart_to_html5({"id": "empty"}))

        rows = [
            {
                "rowIndex": index,
                "isHeader": index == 0,
                "cells": [
                    {
                        "rowIndex": index,
                        "colIndex": 0,
                        "rowSpan": 1,
                        "colSpan": 1,
                        "text": f"R{index}",
                        "blocks": [],
                    }
                ],
            }
            for index in range(31)
        ]
        table = {"type": "table", "tableId": "t-long", "rows": rows, "columnCount": 1}

        self.assertIn("31 rows truncated", "".join(render_table(table, "L2")))
        self.assertIn("<td>R1", "".join(render_table({"rows": rows[:2]}, "L1")))
        with self.assertRaisesRegex(TypeError, "tableId"):
            table_id({"tableId": 123})


class FakePackage:
    def __init__(self, parts: dict[str, bytes]) -> None:
        self.parts = parts

    def exists(self, name: str) -> bool:
        return name in self.parts

    def open_entry(self, name: str) -> BytesIO:
        return BytesIO(self.parts[name])


if __name__ == "__main__":
    unittest.main()
