"""Legacy comment (Note) tests."""

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
    return materialize_bytes(buf.getvalue(), suffix=".xlsx", package="xlsx", name="comments")


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
                    "<text>Approved by auditor</text>"
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
        output = parse_xlsx(data, density="structural")
        self.assertIn("<commentref id=comment0/>", output)
        self.assertIn('<comment id=comment0 cell="A1" author=Alice>', output)
        self.assertIn("Approved by auditor", output)
        # plain omits comments
        plain = parse_xlsx(data, density="plain")
        self.assertNotIn("comment", plain)

    def test_threaded_comments_materialize_empty_cell_and_keep_thread(self) -> None:
        """Modern comments have their own part and must survive even when the cell has no value."""
        threaded_ns = "http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments"
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}"><Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    f'<Relationships xmlns="{NS_RP}"><Relationship Id="r1" Type="{NS_O}/officeDocument" '
                    'Target="xl/workbook.xml"/></Relationships>'
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" xmlns:r="{NS_O}"><sheets>'
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/></sheets></workbook>'
                ),
                "xl/_rels/workbook.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}"><Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/></Relationships>'
                ),
                "xl/worksheets/_rels/sheet1.xml.rels": (
                    f'<Relationships xmlns="{NS_RP}"><Relationship Id="rThread" '
                    'Type="http://schemas.microsoft.com/office/2017/10/relationships/threadedComment" '
                    'Target="../threadedComments/threadedComment1.xml"/></Relationships>'
                ),
                "xl/persons/person.xml": (
                    f'<tc:personList xmlns:tc="{threaded_ns}">'
                    '<tc:person id="p1" displayName="Alice"/><tc:person id="p2" displayName="Bob"/>'
                    "</tc:personList>"
                ),
                "xl/threadedComments/threadedComment1.xml": (
                    f'<tc:ThreadedComments xmlns:tc="{threaded_ns}">'
                    '<tc:threadedComment ref="A2" id="root" personId="p1" dT="2026-08-01T00:00:00Z">'
                    "<tc:text>Review this</tc:text></tc:threadedComment>"
                    '<tc:threadedComment ref="A2" id="reply" parentId="root" personId="p2" done="1">'
                    "<tc:text>Done</tc:text></tc:threadedComment></tc:ThreadedComments>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData><row r="1">'
                    '<c r="A1" t="inlineStr"><is><t>Value</t></is></c>'
                    "</row></sheetData></worksheet>"
                ),
            }
        )
        output = parse_xlsx(data, density="structural")
        self.assertIn("thread-A2-1", output)
        self.assertIn("thread-A2-2", output)
        self.assertIn("author=Alice", output)
        self.assertIn("parent=thread-A2-1 resolved", output)
        self.assertIn('cell="A2"', output)

        plain = parse_xlsx(data, density="plain")
        self.assertIn("[Comment (Bob, reply, resolved): Done]", plain)


if __name__ == "__main__":
    unittest.main()
