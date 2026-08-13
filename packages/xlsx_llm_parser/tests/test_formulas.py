"""Shared formula expansion and array formula tests."""

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


class SharedFormulaTests(unittest.TestCase):
    """Shared formula (t='shared') expansion via si index."""

    def test_slave_cell_gets_expanded_formula(self) -> None:
        """Slave cell B3 acquires formula B3+C3 derived from master B2's B2+C2."""
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
                    # Master: B2 = B2+C2, ref through B2:B4
                    '<row r="2">'
                    '<c r="B2"><f t="shared" ref="B2:B4" si="0">B2+C2</f><v>5</v></c>'
                    "</row>"
                    # Slave: B3 (should expand to B3+C3)
                    '<row r="3"><c r="B3"><f t="shared" si="0"/><v>7</v></c></row>'
                    # Slave: B4 (should expand to B4+C4)
                    '<row r="4"><c r="B4"><f t="shared" si="0"/><v>9</v></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic")
        structural = parse_xlsx(data, density="structural")
        # Master formula unchanged
        self.assertIn('formula="B2+C2"', semantic)
        self.assertIn('formula="B2+C2"', structural)
        # Slave formulas expanded
        self.assertIn('formula="B3+C3"', semantic)
        self.assertIn('formula="B4+C4"', semantic)
        self.assertIn('formula="B3+C3"', structural)
        self.assertIn('formula="B4+C4"', structural)

    def test_absolute_reference_preserved(self) -> None:
        """Absolute references ($col/$row) are not offset."""
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
                    '<row r="1">'
                    '<c r="A1"><f t="shared" ref="A1:A3" si="0">A1*$B$1</f><v>10</v></c>'
                    "</row>"
                    '<row r="2"><c r="A2"><f t="shared" si="0"/><v>20</v></c></row>'
                    '<row r="3"><c r="A3"><f t="shared" si="0"/><v>30</v></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic")
        structural = parse_xlsx(data, density="structural")
        # $B$1 stays absolute
        self.assertIn('formula="A2*$B$1"', semantic)
        self.assertIn('formula="A3*$B$1"', semantic)
        self.assertIn('formula="A2*$B$1"', structural)
        self.assertIn('formula="A3*$B$1"', structural)

    def test_cross_sheet_ref_preserved(self) -> None:
        """Cross-sheet references are not expanded."""
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
                    '<row r="1">'
                    '<c r="A1"><f t="shared" ref="A1:A2" si="0">'
                    "Sheet2!A1+Sheet2!B1"
                    "</f><v>5</v></c>"
                    "</row>"
                    '<row r="2"><c r="A2"><f t="shared" si="0"/><v>7</v></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic")
        structural = parse_xlsx(data, density="structural")
        # Cross-sheet refs preserved verbatim
        self.assertIn('formula="Sheet2!A1+Sheet2!B1"', semantic)
        self.assertIn('formula="Sheet2!A1+Sheet2!B1"', structural)

    def test_function_names_scientific_notation_and_strings_not_offset(self) -> None:
        """Only real cell references are offset: LOG10 stays a function name,
        1E5 stays a number, and text inside string literals is untouched."""
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
                    '<row r="2">'
                    '<c r="B2"><f t="shared" ref="B2:B3" si="0">LOG10(A1)</f><v>1</v></c>'
                    '<c r="C2"><f t="shared" ref="C2:C3" si="1">1E5*A1</f><v>2</v></c>'
                    '<c r="D2"><f t="shared" ref="D2:D3" si="2">"see A1"&amp;A1</f><v>3</v></c>'
                    "</row>"
                    '<row r="3">'
                    '<c r="B3"><f t="shared" si="0"/><v>4</v></c>'
                    '<c r="C3"><f t="shared" si="1"/><v>5</v></c>'
                    '<c r="D3"><f t="shared" si="2"/><v>6</v></c>'
                    "</row>"
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic")
        # Function name intact, only A1 offsets to A2.
        self.assertIn('formula="LOG10(A2)"', semantic)
        # Scientific notation intact.
        self.assertIn('formula="1E5*A2"', semantic)
        # String literal text intact; only the real reference offsets.
        self.assertIn('formula="&quot;see A1&quot;&amp;A2"', semantic)


class ArrayFormulaTests(unittest.TestCase):
    """Array and data table formula type marking."""

    def test_array_formula_marked(self) -> None:
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
                    '<row r="1">'
                    '<c r="A1">'
                    '<f t="array" ref="A1:C3">TRANSPOSE(D1:F3)</f><v>1</v>'
                    "</c>"
                    '<c r="B1"><v>2</v></c><c r="C1"><v>3</v></c>'
                    "</row>"
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic")
        structural = parse_xlsx(data, density="structural")
        self.assertIn("formulaType=array", semantic)
        self.assertIn("formulaRange=A1:C3", semantic)
        self.assertIn("formulaType=array", structural)
        self.assertIn("formulaRange=A1:C3", structural)
        # Classic CSE arrays do not spill: no spillRange/spillFrom markers.
        self.assertNotIn("spillRange", semantic)
        self.assertNotIn("spillFrom", semantic)
        self.assertNotIn("spillRange", structural)

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
        semantic = parse_xlsx(data, density="semantic")
        structural = parse_xlsx(data, density="structural")

        # Source cell has both formulaRange and spillRange
        self.assertIn("spillRange=B1:B3", semantic)
        self.assertIn("spillRange=B1:B3", structural)
        self.assertIn('spillFrom="B1"', semantic)
        self.assertIn('spillFrom="B1"', structural)


if __name__ == "__main__":
    unittest.main()
