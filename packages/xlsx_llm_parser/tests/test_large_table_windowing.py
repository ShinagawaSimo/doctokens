"""Large table windowing via start_row and cell budget truncation."""

import io
import unittest
import zipfile
from pathlib import Path

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
    return materialize_bytes(buf.getvalue(), suffix=".xlsx", package="xlsx", name="large-table")


class WindowingTests(unittest.TestCase):
    def test_start_row_skips_early_rows(self) -> None:
        """An exact A1 range begins at the selected row."""
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
        win = parse_xlsx(data, density="structural", sheet="Data", range_spec="A3:A3")
        self.assertNotIn("Row1", win)
        self.assertNotIn("Row2", win)
        self.assertIn("Row3", win)

    def test_large_sheet_window_with_truncated_marker(self) -> None:
        """Large sheets show a head window plus a truncated marker."""
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
                "xl/worksheets/sheet1.xml": (f'<worksheet xmlns="{NS_S}"><sheetData>{rows_xml}</sheetData></worksheet>'),
            },
        )
        output = parse_xlsx(data, density="structural")
        # Shows data rows within the budget and marks the grid as truncated.
        self.assertIn("<tr row=1>", output)
        self.assertIn("truncated", output)
        # Stops at cell budget; the last row is not shown.
        self.assertNotIn("<tr row=599>", output)


if __name__ == "__main__":
    unittest.main()
