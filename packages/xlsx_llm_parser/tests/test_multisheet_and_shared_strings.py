"""Multi-sheet navigation + shared strings and all cell types."""

import io
import unittest
import zipfile

from xlsx_llm_parser import parse_xlsx

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _make_xlsx(entries: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _wb_xml(sheets: list[tuple[str, int]]) -> str:
    """Build workbook.xml with given (name, sheetId) pairs."""
    sheet_elems = "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rSheet{i}"/>' for n, i in sheets)
    return (
        f'<workbook xmlns="{NS_S}" xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"<sheets>{sheet_elems}</sheets>"
        f"</workbook>"
    )


def _wb_rels(count: int) -> str:
    rows = "".join(
        f'<Relationship Id="rSheet{i}" Type="{NS_O}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, count + 1)
    )
    return f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rows}</Relationships>'


def _sheet_xml(rows: list[str]) -> str:
    return f'<worksheet xmlns="{NS_S}"><sheetData>{"".join(rows)}</sheetData></worksheet>'


def _shared_strings_xml(strings: list[str]) -> str:
    """Build sharedStrings.xml. Rich-text strings are supported via <r> elements."""
    items = []
    for s in strings:
        if "<r>" in s:
            items.append(f"<si>{s}</si>")
        else:
            items.append(f"<si><t>{s}</t></si>")
    count = len(strings)
    return f'<sst xmlns="{NS_S}" count="{count}" uniqueCount="{count}">{"".join(items)}</sst>'


class MultiSheetTests(unittest.TestCase):
    """Workbook navigation — multiple sheets, hidden state, ordering."""

    def test_multiple_sheets_in_order(self) -> None:
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": _wb_xml([("First", 1), ("Second", 2), ("Third", 3)]),
                "xl/_rels/workbook.xml.rels": _wb_rels(3),
                "xl/worksheets/sheet1.xml": _sheet_xml(['<row r="1"><c r="A1" t="inlineStr"><is><t>Sheet1</t></is></c></row>']),
                "xl/worksheets/sheet2.xml": _sheet_xml(['<row r="1"><c r="A1" t="inlineStr"><is><t>Sheet2</t></is></c></row>']),
                "xl/worksheets/sheet3.xml": _sheet_xml([]),
            },
        )
        output = parse_xlsx(data).text
        # Verify order
        first_idx = output.index("First")
        second_idx = output.index("Second")
        third_idx = output.index("Third")
        self.assertLess(first_idx, second_idx)
        self.assertLess(second_idx, third_idx)
        self.assertIn("Sheet1", output)
        self.assertIn("Sheet2", output)

    def test_hidden_sheet(self) -> None:
        """Hidden sheets should have the hidden attribute."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
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
                    '<sheet name="Visible" sheetId="1" r:id="rSheet1"/>'
                    '<sheet name="Hidden" sheetId="2" state="hidden" r:id="rSheet2"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": _wb_rels(2),
                "xl/worksheets/sheet1.xml": _sheet_xml([]),
                "xl/worksheets/sheet2.xml": _sheet_xml([]),
            },
        )
        output = parse_xlsx(data).text
        self.assertIn('<sheet name="Hidden" visibility="hidden" />', output)
        self.assertNotIn("hidden", output.split("Hidden")[0])  # Visible has no hidden


class SharedStringsTests(unittest.TestCase):
    """Shared strings, formula strings, dates, rich text."""

    def test_shared_string_index_out_of_range(self) -> None:
        """Out-of-range SST index produces empty text (no crash)."""
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
                "xl/workbook.xml": _wb_xml([("Data", 1)]),
                "xl/_rels/workbook.xml.rels": _wb_rels(1),
                "xl/sharedStrings.xml": _shared_strings_xml(["OnlyOne"]),
                "xl/worksheets/sheet1.xml": _sheet_xml(['<row r="1"><c r="A1" t="s"><v>99</v></c></row>']),
            },
        )
        output = parse_xlsx(data).text
        # Cell with out-of-range SST index: empty text
        self.assertIn("<cell />", output)

    def test_missing_shared_strings_file(self) -> None:
        """Workbook without sharedStrings.xml should not crash on t='s' cells."""
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
                "xl/workbook.xml": _wb_xml([("Data", 1)]),
                "xl/_rels/workbook.xml.rels": _wb_rels(1),
                "xl/worksheets/sheet1.xml": _sheet_xml(['<row r="1"><c r="A1" t="s"><v>0</v></c></row>']),
            },
        )
        output = parse_xlsx(data).text
        self.assertIn("<cell />", output)

    def test_date_cell(self) -> None:
        """t='d' cells are ISO 8601 dates."""
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
                "xl/workbook.xml": _wb_xml([("Data", 1)]),
                "xl/_rels/workbook.xml.rels": _wb_rels(1),
                "xl/worksheets/sheet1.xml": _sheet_xml(['<row r="1"><c r="A1" t="d"><v>2024-01-15</v></c></row>']),
            },
        )
        output = parse_xlsx(data).text
        self.assertIn("2024-01-15", output)


class MissingReferenceTests(unittest.TestCase):
    """Cells without an r attribute inherit the previous cell's position."""

    def test_cell_without_ref_inherits_position(self) -> None:
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
                "xl/workbook.xml": _wb_xml([("Data", 1)]),
                "xl/_rels/workbook.xml.rels": _wb_rels(1),
                "xl/worksheets/sheet1.xml": _sheet_xml(
                    [
                        '<row r="1">'
                        '<c r="A1" t="inlineStr"><is><t>first</t></is></c>'
                        '<c t="inlineStr"><is><t>second</t></is></c>'
                        "</row>"
                    ]
                ),
            },
        )
        output = parse_xlsx(data).text
        self.assertIn('<tr number="1"><cell>first</cell><cell>second</cell>', output)


if __name__ == "__main__":
    unittest.main()
