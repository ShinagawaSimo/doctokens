"""Hidden rows, hidden columns, and outline tests."""

import io
import unittest
import zipfile

from xlsx_llm_parser import render_workbook

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _make_xlsx(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class HiddenRowTests(unittest.TestCase):
    def test_hidden_row_marked_in_all_densities(self) -> None:
        """Row with hidden='1' outputs <tr row=N hidden>."""
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
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" '
                    'xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
                    "<sheets>"
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Visible</t></is></c></row>'
                    '<row r="2" hidden="1"><c r="A2" t="inlineStr"><is><t>Secret</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        structural = render_workbook(data, density="structural")
        semantic = render_workbook(data, density="semantic")

        # Both densities mark the hidden row
        self.assertIn("<tr row=1>", structural)
        self.assertIn("<tr row=2 hidden>", structural)
        self.assertIn("<tr row=2 hidden>", semantic)
        # plain omits tags entirely
        plain = render_workbook(data, density="plain")
        self.assertIn("Secret", plain)


class HiddenColumnTests(unittest.TestCase):
    def test_hidden_columns_annotated_before_grid(self) -> None:
        """<cols><col hidden='1'> produces <columns ref=X hidden/>."""
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
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" '
                    'xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
                    "<sheets>"
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}">'
                    '<cols><col min="2" max="3" hidden="1"/></cols>'
                    "<sheetData>"
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>A</t></is></c>'
                    '<c r="B1" t="inlineStr"><is><t>B</t></is></c>'
                    '<c r="C1" t="inlineStr"><is><t>C</t></is></c>'
                    "</row>"
                    "</sheetData></worksheet>"
                ),
            },
        )
        structural = render_workbook(data, density="structural")
        # Columns annotation appears before grid
        self.assertIn("<columns ref=B:C hidden>", structural)


class OutlineTests(unittest.TestCase):
    def test_outline_level_and_collapsed_in_semantic(self) -> None:
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
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" '
                    'xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
                    "<sheets>"
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Top</t></is></c></row>'
                    '<row r="2" outlineLevel="1" collapsed="1">'
                    '<c r="A2" t="inlineStr"><is><t>Collapsed</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = render_workbook(data, density="semantic")
        structural = render_workbook(data, density="structural")

        # semantic outputs outline info
        self.assertIn("outlineLevel=1", semantic)
        self.assertIn("collapsed", semantic)

        # structural omits outline info
        self.assertNotIn("outlineLevel", structural)
        self.assertNotIn("collapsed", structural)


if __name__ == "__main__":
    unittest.main()
