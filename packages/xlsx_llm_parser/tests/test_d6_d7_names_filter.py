"""Defined Name and AutoFilter tests."""

import io
import unittest
import zipfile

from xlsx_llm_parser import parse_xlsx

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
        semantic = parse_xlsx(data, density="semantic")
        structural = parse_xlsx(data, density="structural")

        # User names visible in structural and semantic
        self.assertIn("<definedName name=DiscountRate", semantic)
        self.assertIn("<definedName name=TaxRate", semantic)
        self.assertIn("<definedName name=DiscountRate", structural)
        self.assertIn("<definedName name=TaxRate", structural)
        # Built-in _xlnm names skipped
        self.assertNotIn("Print_Area", semantic)
        self.assertNotIn("Print_Area", structural)


class FilterTests(unittest.TestCase):
    def test_filter_range_and_conditions_in_structural(self) -> None:
        """AutoFilter range and conditions appear in structural and semantic."""
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
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}">'
                    '<autoFilter ref="A1:K50">'
                    '<filterColumn colId="0">'
                    '<filters><filter val="East"/><filter val="West"/></filters>'
                    "</filterColumn>"
                    "</autoFilter>"
                    "<sheetData>"
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Region</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        structural = parse_xlsx(data, density="structural")
        semantic = parse_xlsx(data, density="semantic")

        # Both densities show filter range and conditions
        self.assertIn("<filter ref=A1:K50>", structural)
        self.assertIn("<filter ref=A1:K50>", semantic)
        self.assertIn("<condition", semantic)
        self.assertIn("<condition", structural)


if __name__ == "__main__":
    unittest.main()
