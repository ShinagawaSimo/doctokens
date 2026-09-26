"""Merged cell tests — colspan/rowspan in structural and semantic, shadow skip."""

import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

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


class MergeCellTests(unittest.TestCase):
    def _make_merged(self, merge_cells: str, sheet_rows: list[str]) -> bytes:
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
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>{"".join(sheet_rows)}</sheetData>{merge_cells}</worksheet>'
                ),
            },
        )

    def test_structural_and_semantic_output_colspan_rowspan(self) -> None:
        data = self._make_merged(
            '<mergeCells count="1"><mergeCell ref="A1:B2"/></mergeCells>',
            [
                '<row r="1">'
                '<c r="A1" t="inlineStr"><is><t>Title</t></is></c>'
                '<c r="B1" t="inlineStr"><is><t>Shadow</t></is></c>'
                "</row>",
                '<row r="2">'
                '<c r="A2" t="inlineStr"><is><t>Shadow2</t></is></c>'
                '<c r="B2" t="inlineStr"><is><t>Shadow3</t></is></c>'
                "</row>",
            ],
        )
        semantic = parse_xlsx(data, density="semantic").text
        structural = parse_xlsx(data, density="structural").text
        self.assertIn('colspan="2"', semantic)
        self.assertIn('rowspan="2"', semantic)
        self.assertIn('colspan="2"', structural)
        self.assertIn('rowspan="2"', structural)
        # Shadow cells excluded
        self.assertNotIn("Shadow", semantic)
        self.assertNotIn("Shadow", structural)

    def test_structural_skips_shadow_cells(self) -> None:
        data = self._make_merged(
            '<mergeCells count="1"><mergeCell ref="A1:B1"/></mergeCells>',
            [
                '<row r="1">'
                '<c r="A1" t="inlineStr"><is><t>Wide</t></is></c>'
                '<c r="B1" t="inlineStr"><is><t>Hidden</t></is></c>'
                '<c r="C1" t="inlineStr"><is><t>Next</t></is></c>'
                "</row>",
            ],
        )
        output = parse_xlsx(data, density="structural").text
        self.assertIn("Wide", output)
        self.assertNotIn("Hidden", output)
        self.assertIn("Next", output)
        # C1 should use col=C since B1 is shadow (col= expects A1:C1 range)
        self.assertIn('<grid ref="A1:C1">', output)

    def test_rowspan_shadow_does_not_hide_following_cell_position(self) -> None:
        data = self._make_merged(
            '<mergeCells count="1"><mergeCell ref="A1:A2"/></mergeCells>',
            [
                '<row r="1"><c r="A1" t="inlineStr"><is><t>Merged</t></is></c></row>',
                '<row r="2"><c r="A2"/><c r="B2" t="inlineStr"><is><t>Next</t></is></c></row>',
            ],
        )
        output = parse_xlsx(data, density="structural").text
        self.assertIn('column="B"', output)
        grid = ET.fromstring(output).find("./sheet/grid")
        self.assertEqual(grid.find("./tr[@number='1']/cell").attrib, {"rowspan": "2"})
        self.assertEqual(grid.findtext("./tr[@number='1']/cell"), "Merged")
        following = grid.find("./tr[@number='2']/cell")
        self.assertEqual((following.get("column"), following.text), ("B", "Next"))

    def test_no_merge_cells_no_effect(self) -> None:
        data = self._make_merged(
            "",
            [
                '<row r="1"><c r="A1" t="inlineStr"><is><t>Normal</t></is></c></row>',
            ],
        )
        output = parse_xlsx(data, density="semantic").text
        self.assertIn("Normal", output)
        self.assertNotIn("colspan", output)


if __name__ == "__main__":
    unittest.main()
