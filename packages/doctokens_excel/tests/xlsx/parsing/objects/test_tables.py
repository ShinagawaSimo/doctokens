"""Source-query/session ownership for a named table."""

import io
import unittest
import zipfile

from doctokens_excel import open_xlsx, query_xlsx

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


class TableTests(unittest.TestCase):
    def test_named_table_source_query_matches_session_query(self) -> None:
        # This named table supplies the infrastructure condition for two query
        # ownership routes. Ordinary table output belongs to native goldens.
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
                "xl/worksheets/_rels/sheet1.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}">'
                    f'<Relationship Id="rTable1" Type="{NS_O}/table" '
                    'Target="../tables/table1.xml"/>'
                    "</Relationships>"
                ),
                "xl/tables/table1.xml": (
                    f'<table xmlns="{NS_S}" '
                    'name="Sales" displayName="Sales" ref="A1:D5" '
                    'totalsRowCount="1">'
                    '<tableColumns count="3">'
                    '<tableColumn name="Product"/>'
                    '<tableColumn name="Q1"/>'
                    '<tableColumn name="Q2"/>'
                    "</tableColumns>"
                    "</table>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}">'
                    "<sheetData>"
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>P</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        with open_xlsx(data) as session:
            expected = session.query_data(table_id="table-0").text
        self.assertEqual(query_xlsx(data, table_id="table-0").text, expected)


if __name__ == "__main__":
    unittest.main()
