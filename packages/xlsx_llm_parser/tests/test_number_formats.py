"""Number format detection and date-serial decoding tests."""

import io
import unittest
import zipfile

from xlsx_llm_parser import parse_xlsx

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _make_xlsx(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class DateDecodingTests(unittest.TestCase):
    """Built-in date format detection and serial decoding."""

    def _make_date_xlsx(
        self,
        cell_xfs: list[str],
        sheet_rows: list[str],
        *,
        custom_fmts: list[str] | None = None,
    ) -> bytes:
        """Build a minimal XLSX with styles.xml for date format testing."""
        custom_fmts_xml = ""
        if custom_fmts:
            items = "".join(custom_fmts)
            custom_fmts_xml = f'<numFmts count="{len(custom_fmts)}">{items}</numFmts>'
        return _make_xlsx(
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
                    "<workbookPr/>"
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
                "xl/styles.xml": (
                    f'<styleSheet xmlns="{NS_S}">'
                    f"{custom_fmts_xml}"
                    f'<cellXfs count="{len(cell_xfs)}">'
                    f"{''.join(cell_xfs)}"
                    f"</cellXfs>"
                    f"</styleSheet>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
                ),
            },
        )

    def test_missing_styles_file(self) -> None:
        """Workbook without styles.xml falls back to raw values."""
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
                    '<row r="1"><c r="A1" s="0"><v>44927</v></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        output = parse_xlsx(data).text
        self.assertIn("44927", output)

    def test_custom_date_format(self) -> None:
        """Custom format containing 'yyyy' is detected as date."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="164" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>44927</v></c></row>'],
            custom_fmts=['<numFmt numFmtId="164" formatCode="yyyy-mm-dd"/>'],
        )
        output = parse_xlsx(data).text
        self.assertIn("2023-01-01", output)

    def test_quoted_literal_not_detected_as_date(self) -> None:
        """Quoted literal segments ('0 "pcs"') must not trigger date detection."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="164" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>44927</v></c></row>'],
            custom_fmts=['<numFmt numFmtId="164" formatCode=\'0 "pcs"\'/>'],
        )
        output = parse_xlsx(data).text
        self.assertIn("44927", output)
        self.assertNotIn("2023-01-01", output)

    def test_bracket_section_not_detected_as_date(self) -> None:
        """Non-elapsed bracket sections ('[DBNum1]') must not trigger date detection."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="165" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>44927</v></c></row>'],
            custom_fmts=['<numFmt numFmtId="165" formatCode="[DBNum1]0"/>'],
        )
        output = parse_xlsx(data).text
        self.assertIn("44927", output)
        self.assertNotIn("2023-01-01", output)


if __name__ == "__main__":
    unittest.main()
