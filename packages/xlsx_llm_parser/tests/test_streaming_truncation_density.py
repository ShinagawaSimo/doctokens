"""Streaming, truncation, and density tests."""

import io
import unittest
import zipfile
from pathlib import Path

from xlsx_llm_parser import open_xlsx, parse_xlsx

FIXTURES = Path(__file__).resolve().parents[3] / "test_support/fixtures/xlsx"

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _make_xlsx(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class StreamingTests(unittest.TestCase):
    """Session output chunks concatenate to the one-shot render."""

    def test_iter_concat_matches_render(self) -> None:
        data = FIXTURES / "xlsx-formula-relative.xlsx"
        full = parse_xlsx(data).text
        with open_xlsx(data) as workbook:
            streamed = "".join(workbook.iter_render())
        self.assertEqual(full, streamed)

    def test_invalid_density_raises(self) -> None:
        data = FIXTURES / "xlsx-formula-relative.xlsx"
        with self.assertRaises(ValueError):
            parse_xlsx(data, density="semntic")


class TruncationTests(unittest.TestCase):
    """Large sheets produce head+tail with truncated attribute."""

    def _make_sheet(self, num_rows: int) -> bytes:
        rows_xml = [f'<row r="{r}"><c r="A{r}" t="inlineStr"><is><t>Row{r}</t></is></c></row>' for r in range(1, num_rows + 1)]
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
                "xl/worksheets/sheet1.xml": (f'<worksheet xmlns="{NS_S}"><sheetData>{"".join(rows_xml)}</sheetData></worksheet>'),
            },
        )

    def test_large_sheet_windowed(self) -> None:
        """600 rows exceeds cell budget: window plus truncated marker."""
        data = self._make_sheet(600)
        output = parse_xlsx(data).text
        # Shows first rows (within budget) and marks the grid as truncated.
        self.assertIn('<tr number="1">', output)
        self.assertNotIn('<tr number="600">', output)
        self.assertIn("truncated", output)

    def test_range_reading_not_truncated(self) -> None:
        """render_range always shows full results, no truncation."""
        data = self._make_sheet(50)
        output = parse_xlsx(data, sheet="Data", range_spec="A1:A5").text
        self.assertNotIn("truncated", output)
        self.assertIn("Row1", output)
        self.assertIn("Row5", output)

    def test_range_reading_beyond_cell_budget_is_exact(self) -> None:
        """render_range is exact even past the default-view cell budget."""
        data = self._make_sheet(600)
        output = parse_xlsx(data, sheet="Data", range_spec="A1:A600").text
        self.assertIn("Row600", output)
        self.assertNotIn("truncated", output)


if __name__ == "__main__":
    unittest.main()
