"""Number format detection and date-serial decoding tests."""

import io
import unittest
import zipfile
from pathlib import Path

from xlsx_llm_parser import parse_xlsx

from test_support.file_contract import materialize_bytes

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _make_xlsx(entries: dict[str, str]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return materialize_bytes(buf.getvalue(), suffix=".xlsx", package="xlsx", name="number-formats")


class DateDecodingTests(unittest.TestCase):
    """Built-in date format detection and serial decoding."""

    def _make_date_xlsx(
        self,
        cell_xfs: list[str],
        sheet_rows: list[str],
        *,
        date_1904: bool = False,
        custom_fmts: list[str] | None = None,
    ) -> bytes:
        """Build a minimal XLSX with styles.xml for date format testing."""
        date_attr = ' date1904="1"' if date_1904 else ""
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
                    f"<workbookPr{date_attr}/>"
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

    def test_builtin_date_format_14(self) -> None:
        """numFmtId 14 (m/d/yyyy) is detected as date and decoded."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="14" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>44927</v></c></row>'],
        )
        html = parse_xlsx(data)
        # 44927 = 2023-01-01
        self.assertIn("2023-01-01", html)

    def test_builtin_date_format_22(self) -> None:
        """numFmtId 22 (m/d/yyyy h:mm) includes time."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="22" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>44927.5</v></c></row>'],
        )
        html = parse_xlsx(data)
        self.assertIn("2023-01-01", html)

    def test_date_1904_system(self) -> None:
        """Mac date system (1904-based) decodes differently."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="14" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>1</v></c></row>'],
            date_1904=True,
        )
        html = parse_xlsx(data)
        self.assertIn("1904-01-02", html)

    def test_plain_number_not_formatted(self) -> None:
        """numFmtId 0 (General) leaves raw number unchanged."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="0" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>123.456</v></c></row>'],
        )
        html = parse_xlsx(data)
        self.assertIn("123.456", html)

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
        html = parse_xlsx(data)
        self.assertIn("44927", html)

    def test_percentage_format(self) -> None:
        """numFmtId 9 (0%) is detected as percentage."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="9" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>0.125</v></c></row>'],
        )
        html = parse_xlsx(data)
        self.assertIn("12.5%", html)

    def test_custom_date_format(self) -> None:
        """Custom format containing 'yyyy' is detected as date."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="164" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>44927</v></c></row>'],
            custom_fmts=['<numFmt numFmtId="164" formatCode="yyyy-mm-dd"/>'],
        )
        html = parse_xlsx(data)
        self.assertIn("2023-01-01", html)

    def test_quoted_literal_not_detected_as_date(self) -> None:
        """Quoted literal segments ('0 "pcs"') must not trigger date detection."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="164" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>44927</v></c></row>'],
            custom_fmts=['<numFmt numFmtId="164" formatCode=\'0 "pcs"\'/>'],
        )
        html = parse_xlsx(data)
        self.assertIn("44927", html)
        self.assertNotIn("2023-01-01", html)

    def test_bracket_section_not_detected_as_date(self) -> None:
        """Non-elapsed bracket sections ('[DBNum1]') must not trigger date detection."""
        data = self._make_date_xlsx(
            cell_xfs=['<xf numFmtId="165" xfId="0"/>'],
            sheet_rows=['<row r="1"><c r="A1" s="0"><v>44927</v></c></row>'],
            custom_fmts=['<numFmt numFmtId="165" formatCode="[DBNum1]0"/>'],
        )
        html = parse_xlsx(data)
        self.assertIn("44927", html)
        self.assertNotIn("2023-01-01", html)


if __name__ == "__main__":
    unittest.main()
