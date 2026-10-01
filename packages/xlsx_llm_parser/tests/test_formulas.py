"""Shared formula expansion and array formula tests."""

import io
import unittest
import zipfile

from xlsx_llm_parser import parse_xlsx
from xlsx_llm_parser.parsing.modules.worksheets.formulas import (
    _col_row,
    _offset_formula,
    expand_shared_formula_groups,
    expand_shared_formulas,
)

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _make_xlsx(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class SharedFormulaTests(unittest.TestCase):
    """Shared formula (t='shared') expansion via si index."""

    def test_unexpanded_scientific_literal_from_other_producers(self) -> None:
        # Excel canonicalizes this spelling; retain the other-producer exception.
        self.assertEqual(_offset_formula("1E5*A1", 0, 1), "1E5*A2")

    def test_shared_formula_edge_paths(self) -> None:
        cells = [{"ref": "A1", "si": "0"}, {"ref": "A2", "si": "0"}]
        expand_shared_formula_groups({"0": cells})
        self.assertNotIn("formula", cells[1])
        master = {"ref": "A1", "si": "1", "shared_ref": "A1:A2", "formula": ""}
        slave = {"ref": "A2", "si": "1"}
        expand_shared_formula_groups({"1": [master, slave]})
        self.assertEqual(slave["formula"], "")
        # Pending xlsx-formula-sheet-apostrophe.xlsx / xlsx-formula-sheet-cell-name.xlsx.
        self.assertEqual(_offset_formula("'A1'!$B2+'O''Brien'!C$1+数据!D3", 1, 1), "'A1'!$B3+'O''Brien'!D$1+数据!E4")
        expand_shared_formulas([{"ref": "A1"}])
        expand_shared_formula_groups({"2": [{"ref": "A1", "si": "2"}]})
        self.assertEqual(_col_row("bad"), (0, 0))
        self.assertEqual(_offset_formula("A1:B", 1, 1), "B2:B")


class ArrayFormulaTests(unittest.TestCase):
    """Array and data table formula type marking."""

    def test_dynamic_array_spill(self) -> None:
        """Dynamic array: anchor cell marks spillRange, cached recipients get spillFrom."""
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
                    # Anchor: B1 contains the dynamic array formula SORT
                    '<row r="1">'
                    '<c r="B1">'
                    '<f t="array" ref="B1:B3" aca="1">_xlfn.SORT(A1:A3)</f><v>Alice</v>'
                    "</c>"
                    "</row>"
                    # Spill recipients: B2, B3 have cached values but no formula
                    '<row r="2"><c r="B2"><v>Bob</v></c></row>'
                    '<row r="3"><c r="B3"><v>Carol</v></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic").text
        structural = parse_xlsx(data, density="structural").text

        # Source cell has both formulaRange and spillRange
        self.assertIn('spill-range="B1:B3"', semantic)
        self.assertIn('spill-range="B1:B3"', structural)
        self.assertIn('spill-from="B1"', semantic)
        self.assertIn('spill-from="B1"', structural)


if __name__ == "__main__":
    unittest.main()
