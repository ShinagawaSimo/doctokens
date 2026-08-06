"""Legacy comment (Note) tests."""

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


class CommentTests(unittest.TestCase):
    def test_legacy_comment_rendered(self) -> None:
        """Comment on A1 produces inline <commentref> and trailing <comment>."""
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
                    f'<Relationship Id="rComment1" Type="{NS_O}/comments" '
                    'Target="../comments1.xml"/>'
                    "</Relationships>"
                ),
                "xl/comments1.xml": (
                    f'<comments xmlns="{NS_S}">'
                    "<authors><author>Alice</author></authors>"
                    "<commentList>"
                    '<comment ref="A1" authorId="0">'
                    '<text>Approved by auditor</text>'
                    "</comment>"
                    "</commentList>"
                    "</comments>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}">'
                    "<sheetData>"
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Total</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        html = parse_xlsx(data, density="structural")
        self.assertIn("<commentref id=comment0/>", html)
        self.assertIn('<comment id=comment0 cell="A1" author=Alice>', html)
        self.assertIn("Approved by auditor", html)
        # plain omits comments
        plain = parse_xlsx(data, density="plain")
        self.assertNotIn("comment", plain)


if __name__ == "__main__":
    unittest.main()
