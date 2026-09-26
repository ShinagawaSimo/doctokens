"""Data validation, conditional formatting, and external link tests."""

import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

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


class DataValidationTests(unittest.TestCase):
    def test_data_validation_in_structural_and_semantic(self) -> None:
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
                    f'<worksheet xmlns="{NS_S}">'
                    "<dataValidations>"
                    '<dataValidation type="list" sqref="A1:A10" allowBlank="1">'
                    "<formula1>Low,Base,High</formula1>"
                    "</dataValidation>"
                    "</dataValidations>"
                    "<sheetData>"
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic").text
        structural = parse_xlsx(data, density="structural").text
        self.assertIn('<data-validation ref="A1:A10" type="list" />', semantic)
        self.assertIn('<data-validation ref="A1:A10" type="list" />', structural)


class ConditionalFormatTests(unittest.TestCase):
    def test_conditional_format_in_structural_and_semantic(self) -> None:
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
                    f'<worksheet xmlns="{NS_S}">'
                    '<conditionalFormatting sqref="F4:F20">'
                    '<cfRule type="cellIs" priority="1" dxfId="0" stopIfTrue="1" operator="lessThan">'
                    "<formula>F4&lt;0</formula>"
                    "</cfRule>"
                    '<cfRule type="colorScale" priority="2"><colorScale>'
                    '<cfvo type="min"/><cfvo type="max"/>'
                    '<color rgb="FFFF0000"/><color rgb="FF00FF00"/>'
                    "</colorScale></cfRule>"
                    '<cfRule type="dataBar" priority="3"><dataBar minLength="10" showValue="0">'
                    '<cfvo type="min"/><cfvo type="max"/><color rgb="FF638EC6"/>'
                    "</dataBar></cfRule>"
                    '<cfRule type="iconSet" priority="4"><iconSet iconSet="3TrafficLights1" showValue="0">'
                    '<cfvo type="percent" val="0"/><cfvo type="percent" val="33"/>'
                    '<cfvo type="percent" val="67"/>'
                    "</iconSet></cfRule>"
                    '<cfRule type="top10" priority="5" rank="3" percent="1"/>'
                    "</conditionalFormatting>"
                    "<sheetData>"
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
                "xl/styles.xml": (
                    f'<styleSheet xmlns="{NS_S}"><dxfs count="1"><dxf>'
                    '<font><b/><color rgb="FFFF0000"/></font>'
                    '<fill><patternFill><fgColor rgb="FFFFFF00"/></patternFill></fill>'
                    '<numFmt numFmtId="164" formatCode="0.00%"/>'
                    '<alignment horizontal="center" wrapText="1"/>'
                    "</dxf></dxfs></styleSheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic").text
        structural = parse_xlsx(data, density="structural").text
        semantic_root = ET.fromstring(semantic)
        structural_root = ET.fromstring(structural)
        semantic_rules = semantic_root.findall(".//conditional-format/rule")
        structural_rules = structural_root.findall(".//conditional-format/rule")
        first = semantic_rules[0]
        self.assertEqual(first.get("style"), "bold color=#FF0000 fill=#FFFF00 numberFormat=0.00% horizontal=center wrapText=1")
        self.assertIn("stops=type=min:color=FFFF0000", semantic_rules[1].get("details"))
        self.assertIn("minLength=10", semantic_rules[2].get("details"))
        self.assertIn("iconSet=3TrafficLights1", semantic_rules[3].get("details"))
        self.assertEqual(semantic_rules[4].get("rank"), "3")
        self.assertEqual(structural_rules[0].get("type"), "cellIs")
        self.assertEqual(structural_rules[1].get("format"), "colorScale")
        self.assertNotIn("details", structural_rules[1].attrib)


class ExternalLinkTests(unittest.TestCase):
    def test_external_link_detected(self) -> None:
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
                    "<definedNames>"
                    '<definedName name="ExtRef" localSheetId="0">'
                    "'[Budget.xlsx]Sheet1'!$A$1"
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
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic").text
        structural = parse_xlsx(data, density="structural").text
        self.assertIn('<external-link target="Budget.xlsx" />', semantic)
        self.assertIn('<external-link target="Budget.xlsx" />', structural)

    def test_structured_reference_is_not_external_link(self) -> None:
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
                    "<definedNames>"
                    '<definedName name="AvgLifeValues">PopulationSummary[AvgLife]</definedName>'
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
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )

        semantic = parse_xlsx(data, density="semantic").text
        structural = parse_xlsx(data, density="structural").text

        self.assertEqual(ET.fromstring(semantic).find(".//defined-name").text, "PopulationSummary[AvgLife]")
        self.assertNotIn("externalLink", semantic)
        self.assertNotIn("externalLink", structural)


if __name__ == "__main__":
    unittest.main()
