"""B1: minimal XLSX parse + render round-trip."""

import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from xlsx_llm_parser import parse_xlsx, render_workbook

# Minimal XLSX constants
NS_SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _make_xlsx(entries: dict[str, str]) -> bytes:
    """Write entries into an in-memory XLSX ZIP."""
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class B1MinimalParseTests(unittest.TestCase):
    def test_single_sheet_inline_strings_and_numbers(self) -> None:
        """Bare minimum: one sheet with inlineStr and number cells."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="r1" '
                    f'Type="{NS_OFFICE}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_SHEET}" xmlns:r="{NS_REL}">'
                    "<sheets>"
                    '<sheet name="Sheet1" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rSheet1" '
                    f'Type="{NS_OFFICE}/worksheet" Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_SHEET}">'
                    "<sheetData>"
                    '<row r="1">'
                    '<c r="A1" t="inlineStr"><is><t>Product</t></is></c>'
                    '<c r="B1" t="inlineStr"><is><t>Price</t></is></c>'
                    "</row>"
                    '<row r="2">'
                    '<c r="A2" t="inlineStr"><is><t>Widget</t></is></c>'
                    '<c r="B2"><v>99</v></c>'
                    "</row>"
                    '<row r="3">'
                    '<c r="A3" t="inlineStr"><is><t>Gadget</t></is></c>'
                    '<c r="B3"><v>149</v></c>'
                    "</row>"
                    "</sheetData>"
                    "</worksheet>"
                ),
            },
        )

        wb = parse_xlsx(data)
        html = render_workbook(wb)
        self.assertIn("Widget", html)
        self.assertIn("99", html)
        self.assertIn("sheet name=Sheet1", html)
        self.assertIn("<grid ref=A1:B3>", html)

    def test_empty_sheet(self) -> None:
        """Sheet with no data should produce a sheet tag without grid."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="r1" '
                    f'Type="{NS_OFFICE}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_SHEET}" xmlns:r="{NS_REL}">'
                    "<sheets>"
                    '<sheet name="Empty" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rSheet1" '
                    f'Type="{NS_OFFICE}/worksheet" Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_SHEET}"><sheetData/></worksheet>'
                ),
            },
        )

        wb = parse_xlsx(data)
        html = render_workbook(wb)
        self.assertIn("<sheet name=Empty>", html)
        self.assertNotIn("<grid", html)

    def test_boolean_and_error_cells(self) -> None:
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="r1" '
                    f'Type="{NS_OFFICE}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_SHEET}" xmlns:r="{NS_REL}">'
                    "<sheets>"
                    '<sheet name="Sheet1" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rSheet1" '
                    f'Type="{NS_OFFICE}/worksheet" Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_SHEET}">'
                    "<sheetData>"
                    '<row r="1">'
                    '<c r="A1" t="b"><v>1</v></c>'
                    '<c r="B1" t="e"><v>#N/A</v></c>'
                    "</row>"
                    "</sheetData>"
                    "</worksheet>"
                ),
            },
        )
        wb = parse_xlsx(data)
        html = render_workbook(wb)
        self.assertIn("true", html)
        self.assertIn("#N/A", html)


if __name__ == "__main__":
    unittest.main()
