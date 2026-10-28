"""Focused tests for OOXML helpers, resources, and renderer branches."""

from __future__ import annotations

import unittest
import zipfile
from io import BytesIO
from typing import Any, cast
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.relationships import RelationshipIndex
from doctokens_word.docx.model import ParseOptions, ParseWarning, RelationshipRecord
from doctokens_word.docx.ooxml.formatting import (
    is_default_text_color,
    merge_run_formats,
    normalize_hex_color,
    parse_run_format,
    visible_run_format,
)
from doctokens_word.docx.ooxml.numbering import NumberingInstance, NumberingLevel, NumberingMap, NumberingState
from doctokens_word.docx.ooxml.package import PackageReader
from doctokens_word.docx.parsing.modules.resources.assets import IMAGE_REL_TYPE, AssetExtractor
from doctokens_word.docx.parsing.modules.resources.objects import EmbeddedObjectExtractor
from doctokens_word.docx.rendering.objects.charts import chart_to_output, render_chart_resource
from doctokens_word.docx.rendering.objects.smartarts import render_smartart_resource, smartart_to_output
from doctokens_word.docx.rendering.tables.render import render_table, table_id

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class OoxmlFormattingTests(unittest.TestCase):
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


class NumberingAndAssetTests(unittest.TestCase):
    def test_numbering_state_formats_common_numbering_systems(self) -> None:
        formats = [
            ("ordinal", 21, "21st"),
            ("upperLetter", 27, "AA"),
            ("lowerLetter", 28, "bb"),
            ("chineseCounting", 21, "二十一"),
            ("japaneseDigitalTenThousand", 102, "一〇二"),
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

        labels = []
        for index in range(len(formats)):
            label_obj = state.advance("7", index)
            assert label_obj is not None
            labels.append(label_obj["label"])

        self.assertEqual(labels, [expected for _fmt, _start, expected in formats])
        self.assertEqual(warnings[0].code, "UNSUPPORTED_NUMBER_FORMAT")
        self.assertIsNone(state.advance("missing", 0, part="word/document.xml", block_id="b1"))
        self.assertEqual(warnings[-1].code, "NUMBERING_LEVEL_MISSING")

    def test_missing_image_target_warns(self) -> None:
        # A dangling relationship is not a normally saved Office document.
        warnings: list[ParseWarning] = []
        relationships = RelationshipIndex.from_records(
            [
                RelationshipRecord(
                    "word/document.xml",
                    "rMissing",
                    IMAGE_REL_TYPE,
                    "media/missing.png",
                    None,
                    "word/media/missing.png",
                ),
            ]
        )
        AssetExtractor(
            cast(Any, FakePackage({})),
            relationships,
            {"defaults": {}, "overrides": {}},
            warnings,
        ).extract()
        self.assertEqual([warning.code for warning in warnings], ["IMAGE_TARGET_MISSING"])


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
                "categories": [f"Q{index}", f"Q{index + 1}"],
                "values": ["1", "2"],
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

        self.assertIn("categories=Q1,Q2", chart_to_output(cast(Any, chart)))
        self.assertIn("names=Q1,Q2", chart_to_output(cast(Any, {**chart, "chartType": "pie"})))
        self.assertIn("points=12", chart_to_output(cast(Any, {**chart, "chartType": "scatter"})))
        self.assertIn("categories=Q1,Q2", chart_to_output(cast(Any, {**chart, "chartType": "stock"})))
        self.assertIn("names=S1,S2", chart_to_output(cast(Any, {**chart, "chartType": "surface"})))
        self.assertIn("<chart id=empty type=? series=0 truncated>", chart_to_output(cast(Any, {"id": "empty"})))
        chart_output = render_chart_resource(cast(Any, chart))
        chart_resource = ET.fromstring(chart_output)
        chart_node = chart_resource.find(".//chart")
        assert chart_node is not None
        self.assertEqual(chart_node.get("id"), "chartX")
        self.assertEqual(chart_node.get("type"), "bar")
        self.assertEqual(chart_node.get("series"), "6")
        series_node = chart_node.find("series")
        assert series_node is not None
        self.assertEqual(series_node.get("name"), "S1")
        point = series_node.find("point")
        assert point is not None
        self.assertEqual(point.attrib, {"category": "Q1", "value": "1"})

        smartart = {
            "id": "sa1",
            "type": "smartart",
            "part": "word/diagrams/data1.xml",
            "nodeCount": 14,
            "linkCount": 18,
            "rawLinkCount": 18,
            "layoutType": "process",
            "nodes": [{"modelId": f"n{index}", "text": f"Node {index}", "kind": "node"} for index in range(1, 15)],
            "links": [{"from": index, "to": index + 1, "kind": "parOf"} for index in range(1, 19)],
        }

        rendered_sa = smartart_to_output(cast(Any, smartart))
        self.assertIn("truncated", rendered_sa)
        self.assertIn("Node 1", rendered_sa)
        self.assertIn("Node 14", rendered_sa)
        smartart_output = render_smartart_resource(cast(Any, smartart))
        self.assertIn("Node 1", smartart_output)

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

        self.assertIn("<table id=t-long truncated>", "".join(render_table(cast(Any, table), "semantic")))
        self.assertIn(
            "<td>R1",
            "".join(render_table(cast(Any, {"tableId": "t-short", "rows": rows[:2], "columnCount": 1}), "structural")),
        )
        with self.assertRaisesRegex(TypeError, "tableId"):
            table_id(cast(Any, {"tableId": 123}))


class ChartExObjectExtractorTests(unittest.TestCase):
    def test_chart_ex_relationship_populates_docx_object_lookup(self) -> None:
        chart_ex_rel = "http://schemas.microsoft.com/office/2014/relationships/chartEx"
        chart_ex_uri = "http://schemas.microsoft.com/office/drawing/2014/chartex"
        package_bytes = BytesIO()
        with zipfile.ZipFile(package_bytes, "w") as archive:
            archive.writestr(
                "[Content_Types].xml",
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
            )
            archive.writestr(
                "word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>',
            )
            archive.writestr(
                "word/_rels/document.xml.rels",
                f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rChartEx" Type="{chart_ex_rel}" Target="charts/chartEx1.xml"/>'
                "</Relationships>",
            )
            archive.writestr(
                "word/charts/chartEx1.xml",
                f'<cx:chartSpace xmlns:cx="{chart_ex_uri}"><cx:chartData><cx:data id="1">'
                '<cx:strDim type="cat"><cx:lvl ptCount="1"><cx:pt idx="0">East</cx:pt></cx:lvl></cx:strDim>'
                '<cx:numDim type="val"><cx:lvl ptCount="1"><cx:pt idx="0">9</cx:pt></cx:lvl></cx:numDim>'
                "</cx:data></cx:chartData><cx:chart><cx:plotArea><cx:plotAreaRegion>"
                '<cx:series layoutId="sunburst"><cx:dataId val="1"/></cx:series>'
                "</cx:plotAreaRegion></cx:plotArea></cx:chart></cx:chartSpace>",
            )

        with PackageReader(package_bytes.getvalue(), ParseOptions()) as package:
            relationships = RelationshipIndex.from_records(package.read_all_relationships())
            _lookup, charts, _smartarts = EmbeddedObjectExtractor(package, relationships, []).extract()

        self.assertIn("type=sunburst", chart_to_output(cast(Any, charts[0])))


class FakePackage:
    def __init__(self, parts: dict[str, bytes]) -> None:
        self.parts = parts

    def exists(self, name: str) -> bool:
        return name in self.parts

    def open_entry(self, name: str) -> BytesIO:
        return BytesIO(self.parts[name])


if __name__ == "__main__":
    unittest.main()
