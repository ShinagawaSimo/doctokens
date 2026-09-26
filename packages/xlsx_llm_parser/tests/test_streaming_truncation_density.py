"""Streaming, truncation, and density tests."""

import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

from xlsx_llm_parser import open_xlsx, parse_xlsx

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
        full = parse_xlsx(data).text
        with open_xlsx(data) as workbook:
            streamed = "".join(workbook.iter_render())
        self.assertEqual(full, streamed)
        self.assertEqual(ET.fromstring(full).get("density"), "structural")

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
                output = parse_xlsx(data, density=density).text
                if density == "plain":
                    self.assertTrue(output.startswith("density=plain"))
                else:
                    self.assertEqual(ET.fromstring(output).get("density"), density)

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

    def test_small_sheet_not_truncated(self) -> None:
        """10 rows within budget: no truncation."""
        data = self._make_sheet(10)
        output = parse_xlsx(data).text
        self.assertNotIn("truncated", output)

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
        output = parse_xlsx(data, density="plain").text
        self.assertIn("density=plain", output)
        self.assertNotIn("<tr", output)
        self.assertNotIn("<td", output)
        # Tab-separated values
        self.assertIn("A1\tB1", output)
        self.assertIn("A2\tB2", output)


if __name__ == "__main__":
    unittest.main()
