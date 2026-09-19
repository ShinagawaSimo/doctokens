"""Defined Name and AutoFilter tests."""

import io
import unittest
import zipfile
from pathlib import Path

from test_support.api_v2_text import find_xlsx_cells as find_cells
from test_support.api_v2_text import parse_xlsx
from test_support.file_contract import materialize_bytes

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_RP = "http://schemas.openxmlformats.org/package/2006/relationships"


def _make_xlsx(entries: dict[str, str]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return materialize_bytes(buf.getvalue(), suffix=".xlsx", package="xlsx", name="defined-names")


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
        structural = parse_xlsx(data, density="structural")
        self.assertEqual(structural.count("<definedName name=DiscountRate"), 1)
        self.assertEqual(structural.count("<definedName name=TaxRate"), 1)

        matches = find_cells(data, "DiscountRate", kind="definedName")
        self.assertEqual(matches.count("<match "), 1)


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
                    '<filterColumn colId="1"><customFilters and="1">'
                    '<customFilter operator="greaterThan" val="10"/>'
                    '<customFilter operator="lessThanOrEqual" val="100"/>'
                    "</customFilters></filterColumn>"
                    '<filterColumn colId="2"><dynamicFilter type="thisMonth" val="45123"/></filterColumn>'
                    '<filterColumn colId="3"><top10 top="1" percent="1" val="10"/></filterColumn>'
                    '<filterColumn colId="4"><colorFilter dxfId="2" cellColor="0"/></filterColumn>'
                    '<filterColumn colId="5"><iconFilter iconSet="3TrafficLights1" iconId="1"/></filterColumn>'
                    '<filterColumn colId="6"><filters>'
                    '<dateGroupItem year="2026" month="8" dateTimeGrouping="month"/>'
                    "</filters></filterColumn>"
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
        self.assertIn(
            '<condition col=1 type=custom operator="greaterThan" value="10" and/>',
            semantic,
        )
        self.assertIn(
            '<condition col=2 type=dynamic operator="thisMonth" value="45123"/>',
            semantic,
        )
        self.assertIn('<condition col=3 type=top10 rank="10" top percent/>', semantic)
        self.assertIn("<condition col=4 type=color cellColor=0 dxfId=2/>", semantic)
        self.assertIn(
            '<condition col=5 type=icon iconSet="3TrafficLights1" iconId=1/>',
            semantic,
        )
        self.assertIn('type=dateGroup groups="dateTimeGrouping=month:month=8:year=2026"', semantic)
        self.assertNotIn("<condition col=6 type=values/>", semantic)


if __name__ == "__main__":
    unittest.main()
