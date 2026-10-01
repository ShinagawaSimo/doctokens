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
from pptx_llm_parser import open_pptx, parse_pptx
from pptx_llm_parser.core.enums import Density
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parsing.runner import PptxParser


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


def _chart_ex_deck() -> bytes:
    """One Office 2016+ ChartEx waterfall graphic frame."""
    chart_ex_rel = "http://schemas.microsoft.com/office/2014/relationships/chartEx"
    chart_ex_uri = "http://schemas.microsoft.com/office/drawing/2014/chartex"
    chart_ex_shape = f"""<p:graphicFrame>
      <p:nvGraphicFramePr><p:cNvPr id="6" name="Waterfall"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
      <p:xfrm/><a:graphic><a:graphicData uri="{chart_ex_uri}">
        <cx:chart xmlns:cx="{chart_ex_uri}"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="rId2"/>
      </a:graphicData></a:graphic>
    </p:graphicFrame>"""
    chart_part = f"""<cx:chartSpace xmlns:cx="{chart_ex_uri}" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
      <cx:chartData><cx:data id="1"><cx:strDim type="cat"><cx:lvl ptCount="1"><cx:pt idx="0">Start</cx:pt></cx:lvl></cx:strDim>
      <cx:numDim type="val"><cx:lvl ptCount="1"><cx:pt idx="0">10</cx:pt></cx:lvl></cx:numDim></cx:data></cx:chartData>
      <cx:chart><cx:plotArea><cx:plotAreaRegion><cx:series layoutId="waterfall"><cx:dataId val="1"/></cx:series>
      </cx:plotAreaRegion></cx:plotArea></cx:chart>
    </cx:chartSpace>"""
    relation = f'<Relationship Id="rId2" Type="{chart_ex_rel}" Target="../charts/chartEx1.xml"/>'
    return make_pptx(
        {
            "[Content_Types].xml": content_types_xml(
                1,
                extra_defaults=(
                    '<Override PartName="/ppt/charts/chartEx1.xml" ContentType="application/vnd.ms-office.chartex+xml"/>'
                ),
            ),
            "_rels/.rels": root_rels_xml(),
            "ppt/presentation.xml": presentation_xml(1),
            "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
            "ppt/slides/slide1.xml": slide_xml_shapes(chart_ex_shape),
            "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(relation),
            "ppt/charts/chartEx1.xml": chart_part,
        }
    )


class ChartShapeTests(unittest.TestCase):
    def test_plain_chart_placeholder(self) -> None:
        text = parse_pptx(_chart_deck(), density=Density.PLAIN).text
        self.assertIn("[Chart: bar, 2 series]", text)

    def test_chart_ex_output_and_resource(self) -> None:
        source = _chart_ex_deck()
        self.assertIn("[Chart: waterfall, 1 series]", parse_pptx(source, density="plain").text)
        with open_pptx(source) as session:
            self.assertIn("categories=Start values=10", session.render_resource("chart", "chart1").text)

    def test_missing_chart_part_degrades_with_warning(self) -> None:
        parsed = PptxParser().parse(_chart_deck(with_part=False), ParseOptions())
        self.assertTrue(any(w.code == "CHART_PART_MISSING" for w in parsed.warnings))
        text = parse_pptx(_chart_deck(with_part=False), density=Density.PLAIN).text
        self.assertIn("[Chart]", text)


if __name__ == "__main__":
    unittest.main()
