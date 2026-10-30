"""Corrupt comment-part coverage; ordinary comments require native goldens."""

import io
import unittest
import zipfile

from doctokens_excel import parse_xlsx as parse_xlsx_result

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
    def test_malformed_comment_part_surfaces_warning_and_keeps_cells(self) -> None:
        # A truncated comments XML part cannot be saved through Excel's comment UI.
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}"><Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>'
                ),
                "_rels/.rels": (
                    f'<Relationships xmlns="{NS_RP}"><Relationship Id="r1" '
                    f'Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/></Relationships>'
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" xmlns:r="{NS_O}"><sheets>'
                    '<sheet name="Data" sheetId="1" r:id="rSheet"/></sheets></workbook>'
                ),
                "xl/_rels/workbook.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}"><Relationship Id="rSheet" '
                    f'Type="{NS_O}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
                ),
                "xl/worksheets/_rels/sheet1.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}"><Relationship Id="rComment" '
                    f'Type="{NS_O}/comments" Target="../comments1.xml"/></Relationships>'
                ),
                "xl/comments1.xml": "<comments BROKEN",
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData><row r="1">'
                    '<c r="A1" t="inlineStr"><is><t>Total</t></is></c>'
                    "</row></sheetData></worksheet>"
                ),
            }
        )
        result = parse_xlsx_result(data, density="structural")
        self.assertIn("Total", result.text)
        self.assertTrue(
            any(item.code == "COMMENTS_XML_INVALID" and item.locator == "xl/comments1.xml" for item in result.report.warnings)
        )


if __name__ == "__main__":
    unittest.main()
