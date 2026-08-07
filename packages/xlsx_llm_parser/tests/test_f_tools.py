"""find_cells, query_data, and get_resource tests."""

import io
import unittest
import zipfile

from xlsx_llm_parser import find_cells, get_resource, query_data

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_RP = "http://schemas.openxmlformats.org/package/2006/relationships"


def _make_xlsx(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


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
                    'name="Sales" displayName="Sales" ref="A1:B3">'
                    "<tableColumns>"
                    '<tableColumn name="Item"/>'
                    '<tableColumn name="Amount"/>'
                    "</tableColumns>"
                    "</table>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Widget</t></is></c>'
                    '<c r="B1"><v>100</v></c></row>'
                    '<row r="2"><c r="A2" t="inlineStr"><is><t>Gadget</t></is></c>'
                    '<c r="B2"><v>200</v></c></row>'
                    '<row r="3"><c r="A3" t="inlineStr"><is><t>Total</t></is></c>'
                    '<c r="B3"><v>300</v></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        result = query_data(data, table_id="table-0")
        self.assertIn("Widget", result)
        self.assertIn("100", result)
        self.assertIn("<table>", result)


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
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        r = get_resource(data, "image", "image1")
        self.assertIsNotNone(r)
        self.assertIsInstance(r, str)
        self.assertIn("id=image1", r)
        self.assertIn("ref=A1", r)


if __name__ == "__main__":
    unittest.main()
