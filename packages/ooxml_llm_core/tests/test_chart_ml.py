"""Shared ChartML and ChartEx parser coverage."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from ooxml_llm_core.chart_ml import (
    ChartParser,
    _first_dimension,
    _flatten_category_levels,
    _local_name,
    _namespace,
    _safe_int,
    _summary_chart_type,
    _to_float,
    _true_value,
    _unique_in_order,
    parse_chart_xml,
)

NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS_CX = "http://schemas.microsoft.com/office/drawing/2014/chartex"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class ChartParserTests(unittest.TestCase):
    def test_legacy_combination_chart_keeps_plot_and_series_ownership(self) -> None:
        root = ET.fromstring(
            f"""<c:chartSpace xmlns:c="{NS_C}" xmlns:a="{NS_A}">
              <c:chart><c:title><c:tx><c:rich><a:p><a:r><a:t>Revenue</a:t></a:r></a:p>
              </c:rich></c:tx></c:title><c:plotArea>
                <c:barChart><c:ser><c:idx val="0"/><c:tx><c:v>Actual</c:v></c:tx>
                  <c:cat><c:strRef><c:multiLvlStrCache>
                    <c:lvl><c:pt idx="0"><c:v>2025</c:v></c:pt><c:pt idx="1"><c:v>2025</c:v></c:pt></c:lvl>
                    <c:lvl><c:pt idx="0"><c:v>Q1</c:v></c:pt><c:pt idx="1"><c:v>Q2</c:v></c:pt></c:lvl>
                  </c:multiLvlStrCache></c:strRef></c:cat>
                  <c:val><c:numRef><c:f>Sheet1!$B$2:$B$3</c:f><c:numCache>
                    <c:pt idx="0"><c:v>10</c:v></c:pt><c:pt idx="1"><c:v>20</c:v></c:pt>
                  </c:numCache></c:numRef></c:val>
                </c:ser><c:axId val="1"/><c:axId val="2"/></c:barChart>
                <c:lineChart><c:ser><c:idx val="1"/><c:tx><c:v>Forecast</c:v></c:tx>
                  <c:cat><c:strLit><c:pt idx="0"><c:v>Q1</c:v></c:pt></c:strLit></c:cat>
                  <c:val><c:numLit><c:pt idx="0"><c:v>12</c:v></c:pt></c:numLit></c:val>
                </c:ser><c:axId val="1"/><c:axId val="3"/></c:lineChart>
                <c:catAx><c:axId val="1"/><c:title><c:tx><c:rich><a:p><a:r><a:t>Quarter</a:t></a:r></a:p>
                </c:rich></c:tx></c:title></c:catAx>
              </c:plotArea><c:legend><c:legendPos val="b"/></c:legend></c:chart>
            </c:chartSpace>"""
        )

        chart = ChartParser().parse(root)

        self.assertEqual(chart["chart_type"], "combination")
        self.assertEqual([plot["chart_type"] for plot in chart["plots"]], ["bar", "line"])
        self.assertEqual(chart["plots"][0]["series_indices"], [1])
        self.assertEqual(chart["series"][0]["chart_type"], "bar")
        self.assertEqual(chart["series"][1]["chart_type"], "line")
        self.assertEqual(chart["series"][0]["categories"], ["2025 / Q1", "2025 / Q2"])
        self.assertEqual(chart["series"][0]["formula"], "Sheet1!$B$2:$B$3")

    def test_chart_ex_resolves_data_id_and_retains_fallback_metadata(self) -> None:
        root = ET.fromstring(
            f"""<cx:chartSpace xmlns:cx="{NS_CX}" xmlns:a="{NS_A}" xmlns:r="{NS_R}" fallbackImg="rIdPreview">
              <cx:chartData><cx:externalData r:id="rIdWorkbook"/>
                <cx:data id="7">
                  <cx:strDim type="cat"><cx:f>Sheet1!$A$2:$A$3</cx:f><cx:lvl ptCount="2">
                    <cx:pt idx="0">North</cx:pt><cx:pt idx="1">South</cx:pt>
                  </cx:lvl></cx:strDim>
                  <cx:numDim type="val"><cx:f>Sheet1!$B$2:$B$3</cx:f><cx:lvl ptCount="2">
                    <cx:pt idx="0">8</cx:pt><cx:pt idx="1">13</cx:pt>
                  </cx:lvl></cx:numDim>
                </cx:data>
              </cx:chartData>
              <cx:chart><cx:title><cx:rich><a:p><a:r><a:t>Pipeline</a:t></a:r></a:p></cx:rich></cx:title>
                <cx:plotArea><cx:plotAreaRegion><cx:series layoutId="waterfall">
                  <cx:tx><cx:rich><a:p><a:r><a:t>Bookings</a:t></a:r></a:p></cx:rich></cx:tx>
                  <cx:dataId val="7"/><cx:dataLabels/>
                </cx:series></cx:plotAreaRegion><cx:axis id="1" type="cat"/></cx:plotArea>
                <cx:legend pos="r"/>
              </cx:chart>
            </cx:chartSpace>"""
        )

        chart = parse_chart_xml(root)

        self.assertEqual(chart["chart_type"], "waterfall")
        self.assertEqual(chart["title"], "Pipeline")
        self.assertEqual(chart["series"][0]["name"], "Bookings")
        self.assertEqual(chart["series"][0]["categories"], ["North", "South"])
        self.assertEqual(chart["series"][0]["values"], ["8", "13"])
        self.assertEqual(chart["series"][0]["formula"], "Sheet1!$B$2:$B$3")
        self.assertNotIn("plots", chart)

    def test_chart_helpers_and_empty_chart_paths(self) -> None:
        self.assertEqual(ChartParser().parse(ET.Element("chartSpace"))["chart_type"], "unknown")
        self.assertEqual(_flatten_category_levels([["A"], ["1", "2"]]), ["A / 1", "2"])
        self.assertEqual(_summary_chart_type([]), "unknown")
        self.assertEqual(_summary_chart_type(["bar", "bar"]), "bar")
        self.assertEqual(_summary_chart_type(["bar", "line"]), "combination")
        self.assertIsNone(_safe_int("bad"))
        self.assertIsNone(_to_float("bad"))
        self.assertEqual(_to_float("1.5"), 1.5)
        self.assertTrue(_true_value("1"))
        self.assertTrue(_true_value("true"))
        self.assertFalse(_true_value("0"))
        self.assertFalse(_true_value(None))
        self.assertIsNone(_namespace("plain"))
        self.assertEqual(_namespace("{urn:test}tag"), "urn:test")
        self.assertEqual(_local_name("{urn:test}tag"), "tag")
        self.assertEqual(_unique_in_order(["a", "a", "b"]), ["a", "b"])
        self.assertEqual(_first_dimension({}), [])


if __name__ == "__main__":
    unittest.main()
