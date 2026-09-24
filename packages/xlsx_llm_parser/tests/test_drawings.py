"""Drawing, image, chart, and pivot table tests."""

import io
import unittest
import zipfile
from pathlib import Path

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.models import RelationshipRecord
from ooxml_llm_core.package import PackageReader
from xlsx_llm_parser import parse_xlsx as parse_xlsx_result
from xlsx_llm_parser.parsing.modules.worksheets.post import parse_drawings

from test_support.api_v2_text import parse_xlsx
from test_support.file_contract import materialize_bytes

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_RP = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def _make_xlsx(entries: dict[str, str]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return materialize_bytes(buf.getvalue(), suffix=".xlsx", package="xlsx", name="drawings")


def _workbook_with_broken_part(rel_type: str, part_path: str, part_xml: str, extra: dict[str, str] | None = None) -> Path:
    entries = {
        "[Content_Types].xml": (
            f'<Types xmlns="{NS_CT}"><Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>'
        ),
        "_rels/.rels": (
            f'<Relationships xmlns="{NS_RP}"><Relationship Id="r1" Type="{NS_O}/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            f'<workbook xmlns="{NS_S}" xmlns:r="{NS_O}"><sheets>'
            '<sheet name="Data" sheetId="1" r:id="rSheet"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            f'<Relationships xmlns="{NS_RP}"><Relationship Id="rSheet" Type="{NS_O}/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet1.xml": (
            f'<worksheet xmlns="{NS_S}"><sheetData><row r="1">'
            '<c r="A1" t="inlineStr"><is><t>Kept</t></is></c>'
            "</row></sheetData></worksheet>"
        ),
        "xl/worksheets/_rels/sheet1.xml.rels": (
            f'<Relationships xmlns="{NS_RP}"><Relationship Id="rPart" Type="{NS_O}/{rel_type}" '
            f'Target="../{part_path}"/></Relationships>'
        ),
        f"xl/{part_path}": part_xml,
    }
    entries.update(extra or {})
    return _make_xlsx(entries)


class BrokenPartWarningTests(unittest.TestCase):
    def test_broken_sheet_relationships_keep_cells(self) -> None:
        path = _workbook_with_broken_part(
            "drawing", "drawings/drawing1.xml", "<unused", {"xl/worksheets/_rels/sheet1.xml.rels": "<broken"}
        )
        result = parse_xlsx_result(path, density="structural")
        self.assertIn("Kept", result.text)
        self.assertTrue(
            any(w.code == "SHEET_RELS_INVALID" and w.locator == "xl/worksheets/sheet1.xml" for w in result.report.warnings)
        )

    def test_broken_table_and_drawing_keep_cells_with_located_warning(self) -> None:
        for rel_type, part, code in (
            ("table", "tables/table1.xml", "TABLE_XML_INVALID"),
            ("drawing", "drawings/drawing1.xml", "DRAWING_XML_INVALID"),
        ):
            with self.subTest(rel_type=rel_type):
                result = parse_xlsx_result(_workbook_with_broken_part(rel_type, part, "<broken"), density="structural")
                self.assertIn("Kept", result.text)
                self.assertTrue(any(w.code == code and w.locator == f"xl/{part}" for w in result.report.warnings))

    def test_broken_chart_keeps_reference_and_warns(self) -> None:
        drawing = (
            f'<wsDr xmlns="{NS_XDR}" xmlns:c="{NS_C}" xmlns:r="{NS_O}">'
            "<oneCellAnchor><from><col>0</col><row>0</row></from>"
            '<graphicFrame><graphic><graphicData><c:chart r:id="rChart"/>'
            "</graphicData></graphic></graphicFrame></oneCellAnchor></wsDr>"
        )
        extra = {
            "xl/drawings/_rels/drawing1.xml.rels": (
                f'<Relationships xmlns="{NS_RP}"><Relationship Id="rChart" Type="{NS_O}/chart" '
                'Target="../charts/chart1.xml"/></Relationships>'
            ),
            "xl/charts/chart1.xml": "<broken",
        }
        result = parse_xlsx_result(
            _workbook_with_broken_part("drawing", "drawings/drawing1.xml", drawing, extra), density="structural"
        )
        self.assertIn("Kept", result.text)
        self.assertTrue(
            any(w.code == "CHART_XML_INVALID" and w.locator == "xl/charts/chart1.xml" for w in result.report.warnings)
        )


class ImageTests(unittest.TestCase):
    def test_image_anchor_rendered(self) -> None:
        """Picture in drawing produces <image id=... ref=.../>."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" xmlns:r="{NS_O}">'
                    '<sheets><sheet name="Data" sheetId="1" r:id="rSheet1"/></sheets>'
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/_rels/sheet1.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rDraw1" Type="{NS_O}/drawing" '
                    'Target="../drawings/drawing1.xml"/>'
                    "</Relationships>"
                ),
                "xl/drawings/_rels/drawing1.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rImg1" Type="{NS_O}/image" '
                    'Target="../media/image1.png"/>'
                    "</Relationships>"
                ),
                "xl/drawings/drawing1.xml": (
                    f'<wsDr xmlns="{NS_XDR}" xmlns:a="{NS_A}" '
                    f'xmlns:r="{NS_O}">'
                    "<twoCellAnchor>"
                    "<from><col>0</col><row>0</row></from>"
                    "<to><col>2</col><row>1</row></to>"
                    "<pic>"
                    '<blipFill><a:blip r:embed="rImg1"/></blipFill>'
                    "</pic>"
                    "</twoCellAnchor>"
                    "</wsDr>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        output = parse_xlsx(data, density="structural")
        self.assertIn('<img id="image1" ref="A1" />', output)


class ChartTests(unittest.TestCase):
    def test_plain_chart_summary_uses_count_only(self) -> None:
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" xmlns:r="{NS_O}">'
                    '<sheets><sheet name="Data" sheetId="1" r:id="rSheet1"/></sheets>'
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/_rels/sheet1.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rDraw1" Type="{NS_O}/drawing" '
                    'Target="../drawings/drawing1.xml"/>'
                    "</Relationships>"
                ),
                "xl/drawings/_rels/drawing1.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rChart1" Type="{NS_O}/chart" '
                    'Target="../charts/chart1.xml"/>'
                    "</Relationships>"
                ),
                "xl/drawings/drawing1.xml": (
                    f'<wsDr xmlns="{NS_XDR}" xmlns:a="{NS_A}" xmlns:c="{NS_C}" xmlns:r="{NS_O}">'
                    "<twoCellAnchor>"
                    "<from><col>2</col><row>3</row></from>"
                    "<to><col>5</col><row>10</row></to>"
                    '<graphicFrame><a:graphic><a:graphicData><c:chart r:id="rChart1"/></a:graphicData></a:graphic></graphicFrame>'
                    "</twoCellAnchor>"
                    "</wsDr>"
                ),
                "xl/charts/chart1.xml": (
                    f'<c:chartSpace xmlns:c="{NS_C}">'
                    "<c:chart><c:plotArea><c:barChart>"
                    '<c:ser><c:idx val="0"/><c:order val="0"/>'
                    '<c:tx><c:strRef><c:strCache><c:pt idx="0"><c:v>Sales</c:v></c:pt></c:strCache></c:strRef></c:tx>'
                    "</c:ser>"
                    "</c:barChart></c:plotArea></c:chart>"
                    "</c:chartSpace>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )

        plain = parse_xlsx(data, density="plain")
        structural = parse_xlsx(data, density="structural")

        self.assertIn("[Chart: Sales]", plain)
        self.assertNotIn("<chart ", plain)
        self.assertNotIn("series=", plain)
        self.assertNotIn("truncated", plain)
        self.assertIn('<chart id="chart1"', structural)

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
            images, charts = parse_drawings([sheet_rel], package)

        self.assertEqual(images, [])
        self.assertEqual(charts[0]["ref"], "")
        self.assertEqual(charts[0]["type"], "waterfall")
        self.assertEqual(charts[0]["series"][0]["points"][0], {"category": "North", "value": "7"})


class PivotTableTests(unittest.TestCase):
    def test_pivot_detected(self) -> None:
        """Pivot table relationship produces <pivotTable/> marker."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" xmlns:r="{NS_O}">'
                    '<sheets><sheet name="Data" sheetId="1" r:id="rSheet1"/></sheets>'
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/_rels/sheet1.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rPivot1" Type="{NS_O}/pivotTable" '
                    'Target="../pivotTables/pivotTable1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        output = parse_xlsx(data, density="structural")
        self.assertIn('<pivot-table id="pivot1"', output)


if __name__ == "__main__":
    unittest.main()
