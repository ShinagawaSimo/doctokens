"""Focused XLSX tests for the rewritten public boundary."""

from __future__ import annotations

import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

from xlsx_llm_parser import ParseResult, open_xlsx, parse_xlsx

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _workbook() -> bytes:
    entries = {
        "[Content_Types].xml": (
            f'<Types xmlns="{CT}">'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="r" Type="{REL}/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets><sheet name="Sheet1" sheetId="1" r:id="r1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="r1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>"
        ),
        "xl/worksheets/sheet1.xml": (
            f'<worksheet xmlns="{NS}"><sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>Hello</t></is></c></row>'
            "</sheetData></worksheet>"
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class PublicApiV2Tests(unittest.TestCase):
    def test_parse_result_and_session(self) -> None:
        source = _workbook()
        result = parse_xlsx(source)
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(result.report.format, "xlsx")
        self.assertIn("Hello", result.text)
        self.assertEqual(result.syntax_version, "doctokens-xml/1.0")
        self.assertEqual(result.media_type, "application/xml")
        self.assertEqual(ET.fromstring(result.text).tag, "workbook")
        with open_xlsx(source) as session:
            self.assertEqual(session.render(sheet="Sheet1").selection["kind"], "sheet")
        with self.assertRaisesRegex(RuntimeError, "not open"):
            session.render()


if __name__ == "__main__":
    unittest.main()
