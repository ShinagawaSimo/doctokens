"""find_cells, query_data, and get_resource tests."""

import io
import unittest
import zipfile
from pathlib import Path

from xlsx_llm_parser import open_xlsx
from xlsx_llm_parser.api import _render_chart_resource

from test_support.file_contract import materialize_bytes

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_RP = "http://schemas.openxmlformats.org/package/2006/relationships"


def find_cells(source: Path, query: str, **kwargs: object) -> str:
    with open_xlsx(source) as workbook:
        return workbook.find_cells(query, **kwargs).text  # type: ignore[arg-type]


def query_data(source: Path, **kwargs: object) -> str:
    with open_xlsx(source) as workbook:
        return workbook.query_data(**kwargs).text  # type: ignore[arg-type]


def get_resource(source: Path, kind: str, resource_id: str) -> str | bytes:
    with open_xlsx(source) as workbook:
        if kind == "image":
            return workbook.read_resource(kind, resource_id)
        return workbook.render_resource(kind, resource_id).text


def _make_xlsx(entries: dict[str, str]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return materialize_bytes(buf.getvalue(), suffix=".xlsx", package="xlsx", name="tools")


class FindCellsTests(unittest.TestCase):
    def test_find_value(self) -> None:
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
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Revenue</t></is></c></row>'
                    '<row r="2"><c r="B2" t="inlineStr"><is><t>Cost</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        result = find_cells(data, "Revenue")
        self.assertIn("Revenue", result)
        self.assertIn("Data!A1", result)
        self.assertNotIn("Cost", result)

    def test_find_formula_and_defined_name(self) -> None:
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
                    "<definedNames>"
                    '<definedName name="NamedTotal">Data!$B$1</definedName>'
                    "</definedNames>"
                    '<sheets><sheet name="Data" sheetId="1" r:id="rSheet1"/></sheets>'
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Total</t></is></c>'
                    '<c r="B1"><f>SUM(B2:B3)</f><v>3</v></c></row>'
                    '<row r="2"><c r="B2"><v>1</v></c></row>'
                    '<row r="3"><c r="B3"><v>2</v></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )

        formula_result = find_cells(data, "SUM", kind="formula")
        defined_name_result = find_cells(data, "NamedTotal", kind="definedName")

        self.assertIn("field=formula", formula_result)
        self.assertIn("Data!B1", formula_result)
        self.assertIn("NamedTotal", defined_name_result)


class QueryDataTests(unittest.TestCase):
    def test_query_basic(self) -> None:
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
                    f'<Relationship Id="rTable1" Type="{NS_O}/table" '
                    'Target="../tables/table1.xml"/>'
                    "</Relationships>"
                ),
                "xl/tables/table1.xml": (
                    f'<table xmlns="{NS_S}" '
                    'name="Sales" displayName="Sales" ref="A1:B4">'
                    "<tableColumns>"
                    '<tableColumn name="Item"/>'
                    '<tableColumn name="Amount"/>'
                    "</tableColumns>"
                    "</table>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Item</t></is></c>'
                    '<c r="B1" t="inlineStr"><is><t>Amount</t></is></c></row>'
                    '<row r="2"><c r="A2" t="inlineStr"><is><t>Widget</t></is></c>'
                    '<c r="B2"><v>100</v></c></row>'
                    '<row r="3"><c r="A3" t="inlineStr"><is><t>Gadget</t></is></c>'
                    '<c r="B3"><v>200</v></c></row>'
                    '<row r="4"><c r="A4" t="inlineStr"><is><t>Total</t></is></c>'
                    '<c r="B4"><v>300</v></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        result = query_data(data, table_id="table-0")
        self.assertIn("Widget", result)
        self.assertIn("100", result)
        self.assertIn("<table>", result)
        self.assertNotIn("<td>Item", result)

    def test_query_range_with_header_row(self) -> None:
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
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Name</t></is></c>'
                    '<c r="B1" t="inlineStr"><is><t>Amount</t></is></c></row>'
                    '<row r="2"><c r="A2" t="inlineStr"><is><t>Alice</t></is></c>'
                    '<c r="B2"><v>10</v></c></row>'
                    '<row r="3"><c r="A3" t="inlineStr"><is><t>Bob</t></is></c>'
                    '<c r="B3"><v>25</v></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )

        result = query_data(
            data,
            sheet="Data",
            range_spec="A1:B3",
            header_row=1,
            where=[{"column": "Amount", "op": "gt", "value": 20}],
        )

        self.assertIn("Bob", result)
        self.assertNotIn("Alice", result)


class GetResourceTests(unittest.TestCase):
    def test_get_image_resource(self) -> None:
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
                    '<wsDr xmlns="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"'
                    ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
                    f' xmlns:r="{NS_O}">'
                    "<twoCellAnchor>"
                    "<from><col>0</col><row>0</row></from><to><col>2</col><row>1</row></to>"
                    '<pic><blipFill><a:blip r:embed="rImg1"/></blipFill></pic>'
                    "</twoCellAnchor>"
                    "</wsDr>"
                ),
                "xl/media/image1.png": b"image-bytes",
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        r = get_resource(data, "image", "image1")
        self.assertIsNotNone(r)
        assert r is not None
        self.assertIsInstance(r, bytes)

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

        self.assertIn("<chart id=chart1 ref=C3 type=bar series=1 title=Sales>", output)
        self.assertIn("<series index=1 name=Q1 min=1.0 max=2.0>", output)
        self.assertIn("<point category=A value=1/>", output)

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
        self.assertIn("plots=bar,line", output)
        self.assertIn("type=line", output)
        self.assertIn("bubbleSizes=3", output)
        self.assertIn("hidden", output)
        self.assertIn("x=1", output)
        self.assertIn("y=2", output)
        self.assertIn("bubbleSize=3", output)


if __name__ == "__main__":
    unittest.main()
