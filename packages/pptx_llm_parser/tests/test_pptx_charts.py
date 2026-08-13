"""Chart shapes (graphicFrame → chart part via chart_ml) and plain placeholders."""

from __future__ import annotations

import unittest

from _pptx_fixtures import (
    chart_shape_xml,
    chart_xml,
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
)
from pptx_llm_parser import Density, parse_pptx
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parser import PptxParser


def _chart_deck(*, with_part: bool = True) -> bytes:
    rel = (
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" '
        'Target="../charts/chart1.xml"/>'
    )
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(
            1,
            extra_defaults='<Override PartName="/ppt/charts/chart1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>',
        ),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(chart_shape_xml()),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(rel),
    }
    if with_part:
        entries["ppt/charts/chart1.xml"] = chart_xml()
    return make_pptx(entries)


class ChartShapeTests(unittest.TestCase):
    def test_chart_shape_and_chart_record(self) -> None:
        parsed = PptxParser().parse(_chart_deck(), ParseOptions())
        shapes = parsed.slides[0]["shapes"]
        self.assertEqual(len(shapes), 1)
        self.assertEqual(shapes[0]["type"], "chart")
        self.assertEqual(shapes[0]["chartId"], "chart1")
        self.assertEqual(shapes[0]["chartType"], "bar")
        self.assertEqual(shapes[0]["seriesCount"], 2)
        self.assertEqual(shapes[0]["pointCount"], 4)
        self.assertEqual(len(parsed.charts), 1)
        chart = parsed.charts[0]
        self.assertEqual(chart["id"], "chart1")
        self.assertEqual(chart["chart_type"], "bar")
        self.assertEqual(chart["title"], "Sales")
        self.assertEqual(len(chart["series"]), 2)
        self.assertEqual(chart["series"][0]["name"], "Q1")
        self.assertEqual(chart["series"][0]["values"], ["10", "20"])

    def test_plain_chart_placeholder(self) -> None:
        text = parse_pptx(_chart_deck(), density=Density.PLAIN)
        self.assertIn("[Chart: bar, 2 series]", text)

    def test_missing_chart_part_degrades_with_warning(self) -> None:
        parsed = PptxParser().parse(_chart_deck(with_part=False), ParseOptions())
        shape = parsed.slides[0]["shapes"][0]
        self.assertEqual(shape["type"], "chart")
        self.assertNotIn("chartId", shape)
        self.assertTrue(any(w.code == "CHART_PART_MISSING" for w in parsed.warnings))
        text = parse_pptx(_chart_deck(with_part=False), density=Density.PLAIN)
        self.assertIn("[Chart]", text)


if __name__ == "__main__":
    unittest.main()
