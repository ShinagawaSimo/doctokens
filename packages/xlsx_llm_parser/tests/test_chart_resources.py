"""Chart resource output and ChartEx relationship regressions.

Temporary content coverage until the real chart fixtures in the Office checklist exist.
"""

import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.models import RelationshipRecord
from ooxml_llm_core.package import PackageReader
from xlsx_llm_parser.api import _render_chart_resource
from xlsx_llm_parser.parsing.modules.worksheets.drawings import parse_drawings

NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_RP = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _make_xlsx(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class ChartResourceTests(unittest.TestCase):
    def test_chart_ex_drawing_relationship_is_parsed(self) -> None:
        """ChartEx uses a different relation and graphicData namespace than ChartML."""
        chart_ex_rel = "http://schemas.microsoft.com/office/2014/relationships/chartEx"
        chart_ex_uri = "http://schemas.microsoft.com/office/drawing/2014/chartex"
        data = _make_xlsx(
            {
                "[Content_Types].xml": f'<Types xmlns="{NS_CT}"/>',
                "xl/drawings/_rels/drawing1.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}"><Relationship Id="rChartEx" Type="{chart_ex_rel}" '
                    'Target="../charts/chartEx1.xml"/></Relationships>'
                ),
                "xl/drawings/drawing1.xml": (
                    f'<wsDr xmlns="{NS_XDR}" xmlns:a="{NS_A}" xmlns:cx="{chart_ex_uri}" xmlns:r="{NS_O}">'
                    "<absoluteAnchor><graphicFrame><a:graphic><a:graphicData "
                    f'uri="{chart_ex_uri}"><cx:chart r:id="rChartEx"/></a:graphicData>'
                    "</a:graphic></graphicFrame></absoluteAnchor></wsDr>"
                ),
                "xl/charts/chartEx1.xml": (
                    f'<cx:chartSpace xmlns:cx="{chart_ex_uri}"><cx:chartData><cx:data id="1">'
                    '<cx:strDim type="cat"><cx:lvl ptCount="1"><cx:pt idx="0">North</cx:pt></cx:lvl></cx:strDim>'
                    '<cx:numDim type="val"><cx:lvl ptCount="1"><cx:pt idx="0">7</cx:pt></cx:lvl></cx:numDim>'
                    "</cx:data></cx:chartData><cx:chart><cx:plotArea><cx:plotAreaRegion>"
                    '<cx:series layoutId="waterfall"><cx:dataId val="1"/></cx:series>'
                    "</cx:plotAreaRegion></cx:plotArea></cx:chart></cx:chartSpace>"
                ),
            }
        )
        sheet_rel = RelationshipRecord(
            source_part="xl/worksheets/sheet1.xml",
            id="rDrawing",
            type=f"{NS_O}/drawing",
            target="../drawings/drawing1.xml",
            resolved_target="xl/drawings/drawing1.xml",
        )

        with PackageReader(data, PackageLimits()) as package:
            _images, charts = parse_drawings([sheet_rel], package)

        # Temporary final resource coverage until xlsx-chart-waterfall.xlsx exists.
        output = _render_chart_resource(charts[0])
        chart = ET.fromstring(output).find(".//chart")
        assert chart is not None
        self.assertEqual(chart.get("type"), "waterfall")
        point = chart.find("series/point")
        assert point is not None
        self.assertEqual(point.attrib, {"category": "North", "value": "7"})

    def test_render_chart_resource_details(self) -> None:
        output = _render_chart_resource(
            {
                "id": "chart1",
                "ref": "C3",
                "type": "bar",
                "title": "Sales",
                "series_count": 1,
                "series": [
                    {
                        "index": 1,
                        "name": "Q1",
                        "min": 1.0,
                        "max": 2.0,
                        "points": [
                            {"category": "A", "value": "1"},
                            {"category": "B", "value": "2"},
                        ],
                    }
                ],
            }
        )

        chart = ET.fromstring(output).find(".//chart")
        assert chart is not None
        self.assertEqual(chart.attrib, {"id": "chart1", "ref": "C3", "series": "1", "title": "Sales", "type": "bar"})
        series = chart.find("series")
        assert series is not None
        self.assertEqual(series.attrib, {"index": "1", "max": "2.0", "min": "1.0", "name": "Q1"})
        point = series.find("point")
        assert point is not None
        self.assertEqual(point.attrib, {"category": "A", "value": "1"})

    def test_render_chart_optional_fields(self) -> None:
        output = _render_chart_resource(
            {
                "id": "chart2",
                "ref": "D4",
                "type": "combination",
                "plotTypes": ["bar", "line"],
                "series": [
                    {
                        "index": 1,
                        "chartType": "line",
                        "bubbleSizes": ["3"],
                        "xValues": ["1"],
                        "yValues": ["2"],
                        "hidden": True,
                        "points": [{"category": "A", "value": "1", "x": "1", "y": "2", "bubbleSize": "3"}],
                    }
                ],
            }
        )
        chart = ET.fromstring(output).find(".//chart")
        assert chart is not None
        self.assertEqual(chart.get("plots"), "bar,line")
        series = chart.find("series")
        assert series is not None
        self.assertEqual(series.get("type"), "line")
        self.assertEqual(series.get("bubbleSizes"), "3")
        self.assertEqual(series.get("hidden"), "true")
        point = series.find("point")
        assert point is not None
        self.assertEqual(point.get("x"), "1")
        self.assertEqual(point.get("y"), "2")
        self.assertEqual(point.get("bubbleSize"), "3")
