"""XLSX parser — read workbook and worksheet data from an OPC package."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.package import PackageReader

from .models import Cell, ParsedWorkbook, SheetInfo

# SpreadsheetML main namespace
NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def parse_xlsx(source: str | Path | bytes) -> ParsedWorkbook:
    """Parse an XLSX file and return a typed workbook IR."""
    limits = PackageLimits()
    with PackageReader(source, limits) as pkg:
        pkg.validate(required_part="xl/workbook.xml")

        sheets = _parse_workbook(pkg)

        for sheet in sheets:
            sheet["rows"] = _parse_sheet(pkg, sheet["part"])

    return {
        "sheets": sheets,
        "metadata": {
            "source": str(source) if isinstance(source, (str, Path)) else "<bytes>",
        },
    }


def _parse_workbook(pkg: PackageReader) -> list[SheetInfo]:
    """Parse xl/workbook.xml to discover sheet names and worksheet parts."""
    with pkg.open_entry("xl/workbook.xml") as stream:
        root = ET.parse(stream).getroot()

    rels = {r.id: r.resolved_target for r in pkg.read_relationships_for_part("xl/workbook.xml")}

    sheets: list[SheetInfo] = []
    sheets_elem = root.find(f"{{{NS_S}}}sheets")
    if sheets_elem is None:
        return sheets

    for sheet_elem in sheets_elem.findall(f"{{{NS_S}}}sheet"):
        name = sheet_elem.get("name", "")
        rel_id = sheet_elem.get(f"{{{NS_R}}}id", "")
        part = rels.get(rel_id, f"xl/worksheets/sheet{len(sheets) + 1}.xml")
        state = sheet_elem.get("state", "visible")
        sheet_info: SheetInfo = {"name": name, "rows": [], "part": part}
        if state != "visible":
            sheet_info["state"] = state
        sheets.append(sheet_info)

    return sheets


def _parse_sheet(pkg: PackageReader, part: str) -> list[list[Cell]]:
    """Parse a single worksheet XML into typed cell rows.

    Handles cell types:
      - inlineStr (t="inlineStr") — text embedded in the cell element
      - number (t="n" or no t) — numeric value from <v>
      - boolean (t="b") — "1" → true, "0" → false
      - error (t="e") — error code like #DIV/0!
    """
    if not pkg.exists(part):
        return []

    with pkg.open_entry(part) as stream:
        root = ET.parse(stream).getroot()

    sheet_data = root.find(f"{{{NS_S}}}sheetData")
    if sheet_data is None:
        return []

    rows: list[list[Cell]] = []
    for row_elem in sheet_data.findall(f"{{{NS_S}}}row"):
        row_num = int(row_elem.get("r", "0"))
        cells: list[Cell] = []
        for cell_elem in row_elem.findall(f"{{{NS_S}}}c"):
            ref = cell_elem.get("r", "")
            cell_type = cell_elem.get("t", "n")
            col, row = _parse_ref(ref)

            text = ""
            if cell_type == "inlineStr":
                is_elem = cell_elem.find(f"{{{NS_S}}}is")
                if is_elem is not None:
                    t_elem = is_elem.find(f"{{{NS_S}}}t")
                    if t_elem is not None and t_elem.text:
                        text = t_elem.text
            else:
                v_elem = cell_elem.find(f"{{{NS_S}}}v")
                if v_elem is not None and v_elem.text:
                    text = v_elem.text
                    if cell_type == "b":
                        text = "true" if v_elem.text == "1" else "false"

            cell: Cell = {"ref": ref, "row": row_num or row, "col": col, "text": text}
            if cell_type != "n":
                cell["type"] = cell_type
            cells.append(cell)

        rows.append(cells)

    return rows


def _parse_ref(ref: str) -> tuple[int, int]:
    """Parse an A1-style reference into (col, row) as 1-based integers."""
    col_str = ""
    row_str = ""
    for ch in ref:
        if ch.isalpha():
            col_str += ch
        else:
            row_str += ch
    col = 0
    for ch in col_str.upper():
        col = col * 26 + (ord(ch) - ord("A") + 1)
    row = int(row_str) if row_str else 0
    return col, row
