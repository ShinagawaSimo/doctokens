"""Large table windowing via start_row and cell budget truncation."""

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


class WindowingTests(unittest.TestCase):
    def test_start_row_skips_early_rows(self) -> None:
        """start_row=3 begins rendering from row 3."""
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
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Row1</t></is></c></row>'
                    '<row r="2"><c r="A2" t="inlineStr"><is><t>Row2</t></is></c></row>'
                    '<row r="3"><c r="A3" t="inlineStr"><is><t>Row3</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        # Full read
        full = parse_xlsx(data, density="structural")
        self.assertIn("Row1", full)
        self.assertIn("Row3", full)
        # Window from row 3
        win = parse_xlsx(data, density="structural", start_row=3)
        self.assertNotIn("Row1", win)
        self.assertNotIn("Row2", win)
        self.assertIn("Row3", win)

    def test_large_sheet_not_fully_truncated(self) -> None:
        """Large sheets now show a window instead of bare truncated marker."""
        rows_xml = ""
        for r in range(1, 600):  # 599 rows × 1 cell = 599 > _CELL_BUDGET=500
            rows_xml += f'<row r="{r}"><c r="A{r}" t="inlineStr"><is><t>R{r}</t></is></c></row>'
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
                    f'<worksheet xmlns="{NS_S}"><sheetData>{rows_xml}</sheetData></worksheet>'
                ),
            },
        )
        html = parse_xlsx(data, density="structural")
        # Shows data rows (not bare truncated)
        self.assertIn("<tr row=1>", html)
        # Stops at cell budget, last row shown is around row 500-502
        self.assertNotIn("<tr row=599>", html)
        self.assertIn("<tr row=1>", html)


if __name__ == "__main__":
    unittest.main()
