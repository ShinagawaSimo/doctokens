"""Defined Name and AutoFilter tests."""

import io
import unittest
import zipfile

from doctokens_excel import open_xlsx, parse_xlsx

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


class DefinedNameTests(unittest.TestCase):
    def test_user_defined_name_in_structural_and_semantic(self) -> None:
        """User-defined name appears in structural and semantic."""
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
                    f'<workbook xmlns="{NS_S}" '
                    f'xmlns:r="{NS_O}">'
                    "<sheets>"
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "<definedNames>"
                    '<definedName name="DiscountRate">0.08</definedName>'
                    '<definedName name="TaxRate" localSheetId="0">'
                    "'Data'!$B$1"
                    "</definedName>"
                    '<definedName name="_xlnm.Print_Area" localSheetId="0" hidden="1">'
                    "Data!$A$1:$D$10"
                    "</definedName>"
                    "</definedNames>"
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
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Hi</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic").text
        structural = parse_xlsx(data, density="structural").text

        # User names visible in structural and semantic
        self.assertIn('<defined-name name="DiscountRate">', semantic)
        self.assertIn('<defined-name name="TaxRate">', semantic)
        self.assertIn('<defined-name name="DiscountRate">', structural)
        self.assertIn('<defined-name name="TaxRate">', structural)
        # Built-in _xlnm names skipped
        self.assertNotIn("Print_Area", semantic)
        self.assertNotIn("Print_Area", structural)

    def test_global_name_emitted_once_across_sheets(self) -> None:
        """Global names are emitted once; find_cells reports them once."""
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
                    f'<workbook xmlns="{NS_S}" '
                    f'xmlns:r="{NS_O}">'
                    "<sheets>"
                    '<sheet name="S1" sheetId="1" r:id="rSheet1"/>'
                    '<sheet name="S2" sheetId="2" r:id="rSheet2"/>'
                    "</sheets>"
                    "<definedNames>"
                    '<definedName name="DiscountRate">0.08</definedName>'
                    '<definedName name="TaxRate" localSheetId="0">S1!$B$1</definedName>'
                    "</definedNames>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    f'<Relationship Id="rSheet2" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet2.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (f'<worksheet xmlns="{NS_S}"><sheetData/></worksheet>'),
                "xl/worksheets/sheet2.xml": (f'<worksheet xmlns="{NS_S}"><sheetData/></worksheet>'),
            },
        )
        structural = parse_xlsx(data, density="structural").text
        self.assertEqual(structural.count('<defined-name name="DiscountRate">'), 1)
        self.assertEqual(structural.count('<defined-name name="TaxRate">'), 1)

        with open_xlsx(data) as workbook:
            matches = workbook.find_cells("DiscountRate", kind="definedName").text
        self.assertEqual(matches.count("<match "), 1)


if __name__ == "__main__":
    unittest.main()
