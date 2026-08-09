"""Minimal XLSX parse + render round-trip."""

import io
import unittest
import zipfile

from xlsx_llm_parser import parse_xlsx

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _make_xlsx(entries: dict[str, str]) -> bytes:
    """Write entries into an in-memory XLSX ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _content_types() -> str:
    return (
        f'<Types xmlns="{NS_CT}">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType='
        '"application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'spreadsheetml.sheet.main+xml"/>'
        "</Types>"
    )


def _root_rels() -> str:
    return (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rSheet{i}"/>' for i, n in enumerate(sheet_names, start=1))
    return f'<workbook xmlns="{NS_S}" xmlns:r="{NS_R}"><sheets>{sheets}</sheets></workbook>'


def _workbook_rels(sheet_count: int) -> str:
    rows = "".join(
        f'<Relationship Id="rSheet{i}" Type="{NS_O}/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, sheet_count + 1)
    )
    return f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rows}</Relationships>'


def _sheet_xml(rows: list[str]) -> str:
    return f'<worksheet xmlns="{NS_S}"><sheetData>{"".join(rows)}</sheetData></worksheet>'


class MinimalParseTests(unittest.TestCase):
    def test_single_sheet_inline_strings_and_numbers(self) -> None:
        """Inline strings and plain number cells."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": _content_types(),
                "_rels/.rels": _root_rels(),
                "xl/workbook.xml": _workbook_xml(["Sheet1"]),
                "xl/_rels/workbook.xml.rels": _workbook_rels(1),
                "xl/worksheets/sheet1.xml": _sheet_xml(
                    [
                        '<row r="1">'
                        '<c r="A1" t="inlineStr"><is><t>Product</t></is></c>'
                        '<c r="B1" t="inlineStr"><is><t>Price</t></is></c>'
                        "</row>",
                        '<row r="2"><c r="A2" t="inlineStr"><is><t>Widget</t></is></c><c r="B2"><v>99</v></c></row>',
                    ]
                ),
            },
        )

        html = parse_xlsx(data)
        self.assertIn("Widget", html)
        self.assertIn("99", html)
        self.assertIn("sheet name=Sheet1", html)
        self.assertIn("<grid ref=A1:B2>", html)
        self.assertIn("<tr row=1>", html)
        self.assertIn("<tr row=2>", html)

    def test_empty_sheet(self) -> None:
        """Sheet with no rows produces a sheet tag without grid."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": _content_types(),
                "_rels/.rels": _root_rels(),
                "xl/workbook.xml": _workbook_xml(["Empty"]),
                "xl/_rels/workbook.xml.rels": _workbook_rels(1),
                "xl/worksheets/sheet1.xml": _sheet_xml([]),
            },
        )
        html = parse_xlsx(data)
        self.assertIn("<sheet name=Empty>", html)
        self.assertNotIn("<grid", html)

    def test_boolean_and_error_cells(self) -> None:
        """Boolean and error cell types."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": _content_types(),
                "_rels/.rels": _root_rels(),
                "xl/workbook.xml": _workbook_xml(["Sheet1"]),
                "xl/_rels/workbook.xml.rels": _workbook_rels(1),
                "xl/worksheets/sheet1.xml": _sheet_xml(
                    ['<row r="1"><c r="A1" t="b"><v>1</v></c><c r="B1" t="e"><v>#N/A</v></c></row>']
                ),
            },
        )
        html = parse_xlsx(data)
        self.assertIn("true", html)
        self.assertIn("#N/A", html)


if __name__ == "__main__":
    unittest.main()
