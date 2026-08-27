"""Streaming, truncation, and density tests."""

import io
import unittest
import zipfile
from pathlib import Path

from xlsx_llm_parser import iter_workbook, parse_xlsx, render_range

from test_support.file_contract import materialize_bytes, output_path, write_text_result

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _make_xlsx(entries: dict[str, str]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return materialize_bytes(buf.getvalue(), suffix=".xlsx", package="xlsx", name="streaming")


class StreamingTests(unittest.TestCase):
    """parse_xlsx stream=True chunk concatenation matches full render."""

    def test_iter_concat_matches_render(self) -> None:
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
                    '<sheet name="S1" sheetId="1" r:id="rSheet1"/>'
                    '<sheet name="S2" sheetId="2" r:id="rSheet2"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    f'<Relationship Id="rSheet2" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet2.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
                "xl/worksheets/sheet2.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>Y</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        full = parse_xlsx(data)
        streamed = "".join(parse_xlsx(data, stream=True))
        self.assertEqual(full, streamed)
        self.assertEqual(full, "".join(iter_workbook(data)))
        self.assertIn("density=structural", full)

    def test_density_marker_emitted(self) -> None:
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
                    '<sheet name="S" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (f'<worksheet xmlns="{NS_S}"><sheetData/></worksheet>'),
            },
        )
        for density in ("plain", "structural"):
            with self.subTest(density=density):
                output = parse_xlsx(data, density=density)
                self.assertTrue(output.startswith(f"density={density}"))

    def test_invalid_density_raises(self) -> None:
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
                    '<sheet name="S" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (f'<worksheet xmlns="{NS_S}"><sheetData/></worksheet>'),
            },
        )
        with self.assertRaises(ValueError):
            parse_xlsx(data, density="semntic")


class TestOutputMaterializationTests(unittest.TestCase):
    def test_test_adapter_writes_full_render_atomically(self) -> None:
        """The test adapter writes parsed output without a production file API."""
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
                    '<sheet name="S" sheetId="1" r:id="rSheet1"/>'
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
                    '<row r="1"><c r="A1" t="inlineStr"><is><t>X</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        output_dir = output_path("xlsx", "write-document", "parsed.html").parent
        path = write_text_result(parse_xlsx(data), output_dir / "parsed.html")
        self.assertEqual(path.name, "parsed.html")
        self.assertEqual(path.read_text(encoding="utf-8"), parse_xlsx(data))
        self.assertEqual(list(output_dir.glob(".*.tmp")), [])


class TruncationTests(unittest.TestCase):
    """Large sheets produce head+tail with truncated attribute."""

    def _make_sheet(self, num_rows: int) -> Path:
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

    def test_small_sheet_not_truncated(self) -> None:
        """10 rows within budget: no truncation."""
        data = self._make_sheet(10)
        output = parse_xlsx(data)
        self.assertNotIn("truncated", output)

    def test_large_sheet_windowed(self) -> None:
        """600 rows exceeds cell budget: window plus truncated marker."""
        data = self._make_sheet(600)
        output = parse_xlsx(data)
        # Shows first rows (within budget) and marks the grid as truncated.
        self.assertIn("<tr row=1>", output)
        self.assertNotIn("<tr row=600>", output)
        self.assertIn("truncated", output)

    def test_range_reading_not_truncated(self) -> None:
        """render_range always shows full results, no truncation."""
        data = self._make_sheet(50)
        output = render_range(data, "Data", "A1:A5")
        self.assertNotIn("truncated", output)
        self.assertIn("Row1", output)
        self.assertIn("Row5", output)

    def test_range_reading_beyond_cell_budget_is_exact(self) -> None:
        """render_range is exact even past the default-view cell budget."""
        data = self._make_sheet(600)
        output = render_range(data, "Data", "A1:A600")
        self.assertIn("Row600", output)
        self.assertNotIn("truncated", output)


class PlainDensityTests(unittest.TestCase):
    """Plain text density — tab-separated values."""

    def test_plain_no_tags(self) -> None:
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
                    '<sheet name="D" sheetId="1" r:id="rSheet1"/>'
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
                    '<row r="1">'
                    '<c r="A1" t="inlineStr"><is><t>A1</t></is></c>'
                    '<c r="B1" t="inlineStr"><is><t>B1</t></is></c>'
                    "</row>"
                    '<row r="2">'
                    '<c r="A2" t="inlineStr"><is><t>A2</t></is></c>'
                    '<c r="B2" t="inlineStr"><is><t>B2</t></is></c>'
                    "</row>"
                    "</sheetData></worksheet>"
                ),
            },
        )
        output = parse_xlsx(data, density="plain")
        self.assertIn("density=plain", output)
        self.assertNotIn("<tr", output)
        self.assertNotIn("<td", output)
        # Tab-separated values
        self.assertIn("A1\tB1", output)
        self.assertIn("A2\tB2", output)


if __name__ == "__main__":
    unittest.main()
