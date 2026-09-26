"""Hyperlink tests — external URLs and internal references."""

import io
import unittest
import zipfile

from xlsx_llm_parser import open_xlsx, parse_xlsx

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_RP = "http://schemas.openxmlformats.org/package/2006/relationships"
# Relationship type for hyperlinks
REL_HYPERLINK = f"{NS_O}/hyperlink"


def _make_xlsx(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class HyperlinkTests(unittest.TestCase):
    def test_external_url_rendered_as_anchor(self) -> None:
        """External hyperlink via relationship → <a href='https://...'>."""
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
                    f'<worksheet xmlns="{NS_S}"'
                    f' xmlns:r="{NS_O}">'
                    "<sheetData>"
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Click</t></is></c></row>'
                    "</sheetData>"
                    "<hyperlinks>"
                    f'<hyperlink ref="A1" r:id="rLink1"/>'
                    "</hyperlinks>"
                    "</worksheet>"
                ),
                "xl/worksheets/_rels/sheet1.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rLink1" Type="{REL_HYPERLINK}" '
                    'Target="https://example.com" TargetMode="External"/>'
                    "</Relationships>"
                ),
            },
        )
        output = parse_xlsx(data, density="structural").text
        self.assertIn('<a href="https://example.com">Click</a>', output)
        semantic = parse_xlsx(data, density="semantic").text
        self.assertIn('<a href="https://example.com">Click</a>', semantic)
        with open_xlsx(data) as workbook:
            matches = workbook.find_cells("example.com", kind="hyperlink").text
        self.assertIn("field=hyperlink", matches)
        self.assertIn("https://example.com", matches)

    def test_internal_location_rendered_as_anchor(self) -> None:
        """Internal hyperlink via location → <a href='#Sheet2!A1'>."""
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
                    f'<worksheet xmlns="{NS_S}"'
                    f' xmlns:r="{NS_O}">'
                    "<sheetData>"
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Go</t></is></c></row>'
                    "</sheetData>"
                    f'<hyperlinks><hyperlink ref="A1" location="Sheet2!B5"/></hyperlinks>'
                    "</worksheet>"
                ),
            },
        )
        output = parse_xlsx(data, density="structural").text
        self.assertIn('<a href="#Sheet2!B5">Go</a>', output)


if __name__ == "__main__":
    unittest.main()
