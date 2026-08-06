"""Drawing, image, chart, and pivot table tests."""

import io
import unittest
import zipfile

from xlsx_llm_parser import parse_xlsx

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
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
                    "<sheets><sheet name=\"Data\" sheetId=\"1\" r:id=\"rSheet1\"/></sheets>"
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
                    "<blipFill><a:blip r:embed=\"rImg1\"/></blipFill>"
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
        html = parse_xlsx(data, density="structural")
        self.assertIn("<image id=image1 ref=A1/>", html)


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
                    "<sheets><sheet name=\"Data\" sheetId=\"1\" r:id=\"rSheet1\"/></sheets>"
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
        html = parse_xlsx(data, density="structural")
        self.assertIn("<pivotTable id=pivot1", html)


if __name__ == "__main__":
    unittest.main()
