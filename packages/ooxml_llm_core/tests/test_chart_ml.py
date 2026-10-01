"""Temporary combination/multilevel chart coverage pending xlsx-chart-combination.xlsx and xlsx-chart-multilevel.xlsx.
Invalid values and empty chart parts remain exceptions.
"""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from ooxml_llm_core._chart_values import _flatten_category_levels, _safe_int, _to_float
from ooxml_llm_core.chart_ml import (
    ChartParser,
    _first_dimension,
    _namespace,
    _summary_chart_type,
    _true_value,
)

NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


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

        self.assertEqual(chart["series"][0]["chart_type"], "bar")
        self.assertEqual(chart["series"][1]["chart_type"], "line")
        self.assertEqual(chart["series"][0]["categories"], ["2025 / Q1", "2025 / Q2"])

    def test_chart_helpers_and_empty_chart_paths(self) -> None:
        self.assertEqual(ChartParser().parse(ET.Element("chartSpace"))["chart_type"], "unknown")
        self.assertEqual(_flatten_category_levels([["A"], ["1", "2"]]), ["A / 1", "2"])
        self.assertEqual(_summary_chart_type([]), "unknown")
        self.assertIsNone(_safe_int("bad"))
        self.assertIsNone(_to_float("bad"))
        self.assertFalse(_true_value(None))
        self.assertIsNone(_namespace("plain"))
        self.assertEqual(_first_dimension({}), [])


if __name__ == "__main__":
    unittest.main()
