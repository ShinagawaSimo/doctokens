"""XLSX parser — read workbook and worksheet data from an OPC package."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.package import PackageReader

from .formats import FormatIndex, parse_styles
from .models import Cell, ParsedWorkbook, SheetInfo
from .share_formulas import expand_shared_formulas

# SpreadsheetML main namespace
NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Relationship types for sheet kind detection
_REL_WORKSHEET = f"{NS_R}/worksheet"
_REL_CHARTSHEET = f"{NS_R}/chartsheet"


def parse_xlsx(source: str | Path | bytes) -> ParsedWorkbook:
    """Parse an XLSX file and return a typed workbook IR."""
    limits = PackageLimits()
    with PackageReader(source, limits) as pkg:
        pkg.validate(required_part="xl/workbook.xml")

        date_1904, sheets = _parse_workbook(pkg)
        sst = _parse_shared_strings(pkg)
        fmt_index = parse_styles(pkg)
        fmt_index.set_date_system(date_1904)

        for sheet in sheets:
            if sheet.get("kind") != "chartsheet":
                sheet["rows"] = _parse_sheet(pkg, sheet["part"], sst, fmt_index)

    return {
        "sheets": sheets,
        "metadata": {
            "source": str(source) if isinstance(source, (str, Path)) else "<bytes>",
        },
    }


def _parse_workbook(pkg: PackageReader) -> tuple[bool, list[SheetInfo]]:
    """Parse xl/workbook.xml for date system, sheet names, and part targets.

    Returns (date_1904, sheets).
    """
    with pkg.open_entry("xl/workbook.xml") as stream:
        root = ET.parse(stream).getroot()

    # Date system: 1900 (default) or 1904 (Mac)
    wb_pr = root.find(f"{{{NS_S}}}workbookPr")
    date_1904 = wb_pr is not None and wb_pr.get("date1904") == "1"

    # Build a lookup of rel_id → (resolved_target, rel_type)
    rels = {
        r.id: (r.resolved_target, r.type)
        for r in pkg.read_relationships_for_part("xl/workbook.xml")
    }

    sheets: list[SheetInfo] = []
    sheets_elem = root.find(f"{{{NS_S}}}sheets")
    if sheets_elem is None:
        return date_1904, sheets

    for sheet_elem in sheets_elem.findall(f"{{{NS_S}}}sheet"):
        name = sheet_elem.get("name", "")
        rel_id = sheet_elem.get(f"{{{NS_R}}}id", "")
        rel_info = rels.get(rel_id)
        part, rel_type = rel_info if rel_info else (
            f"xl/worksheets/sheet{len(sheets) + 1}.xml",
            _REL_WORKSHEET,
        )
        state = sheet_elem.get("state", "visible")

        kind = "chartsheet" if rel_type == _REL_CHARTSHEET else "worksheet"
        sheet_info: SheetInfo = {"name": name, "rows": [], "part": part, "kind": kind}
        if state != "visible":
            sheet_info["state"] = state
        sheets.append(sheet_info)

    return date_1904, sheets


def _parse_shared_strings(pkg: PackageReader) -> list[str]:
    """Parse xl/sharedStrings.xml into an ordered list of string values.

    Each <si> element may contain a plain <t> or rich-text <r> runs.
    For rich text only the concatenated text is kept; formatting is ignored.
    """
    if not pkg.exists("xl/sharedStrings.xml"):
        return []

    with pkg.open_entry("xl/sharedStrings.xml") as stream:
        root = ET.parse(stream).getroot()

    strings: list[str] = []
    for si in root.findall(f"{{{NS_S}}}si"):
        # Plain text: <si><t>value</t></si>
        t_elem = si.find(f"{{{NS_S}}}t")
        if t_elem is not None:
            strings.append(t_elem.text or "")
        else:
            # Rich text: <si><r><t>part1</t></r><r><t>part2</t></r></si>
            parts = [
                rt.text or ""
                for r_elem in si.findall(f"{{{NS_S}}}r")
                for rt in r_elem.findall(f"{{{NS_S}}}t")
                if rt.text
            ]
            strings.append("".join(parts))

    return strings


def _parse_sheet(
    pkg: PackageReader, part: str, sst: list[str], fmt_index: FormatIndex | None = None
) -> list[list[Cell]]:
    """Parse a single worksheet XML into typed cell rows.

    Handles all ECMA-376 cell types and applies number formatting.
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
                # Text embedded directly in the cell
                is_elem = cell_elem.find(f"{{{NS_S}}}is")
                if is_elem is not None:
                    t_elem = is_elem.find(f"{{{NS_S}}}t")
                    if t_elem is not None and t_elem.text:
                        text = t_elem.text
            elif cell_type == "s":
                # Shared string index
                v_elem = cell_elem.find(f"{{{NS_S}}}v")
                if v_elem is not None and v_elem.text:
                    try:
                        idx = int(v_elem.text)
                        if 0 <= idx < len(sst):
                            text = sst[idx]
                    except ValueError:
                        pass
            else:
                # n, str, b, e, d — all read from <v>
                v_elem = cell_elem.find(f"{{{NS_S}}}v")
                if v_elem is not None and v_elem.text:
                    text = v_elem.text
                    if cell_type == "b":
                        text = "true" if v_elem.text == "1" else "false"

            # Apply number formatting for numeric cells with a style
            if fmt_index is not None and cell_type == "n" and text:
                style_str = cell_elem.get("s")
                if style_str is not None:
                    try:
                        text = fmt_index.format_value(int(style_str), text)
                    except (ValueError, IndexError):
                        pass

            # Extract formula if present
            f_elem = cell_elem.find(f"{{{NS_S}}}f")
            formula = None
            formula_meta: dict = {}
            if f_elem is not None:
                f_type = f_elem.get("t", "")
                if f_type == "shared":
                    si = f_elem.get("si")
                    ref_range = f_elem.get("ref")
                    if ref_range:
                        formula_meta["shared_ref"] = ref_range
                        formula_meta["si"] = si
                    elif si is not None:
                        formula_meta["si"] = si
                    if f_elem.text:
                        formula = f_elem.text
                elif f_type == "array":
                    formula_meta["formulaType"] = "array"
                    ref_range = f_elem.get("ref", "")
                    if ref_range:
                        formula_meta["formulaRange"] = ref_range
                    if f_elem.text:
                        formula = f_elem.text
                elif f_type == "dataTable":
                    formula_meta["formulaType"] = "dataTable"
                    if f_elem.text:
                        formula = f_elem.text
                elif f_elem.text:
                    formula = f_elem.text

            cell: Cell = {"ref": ref, "row": row_num or row, "col": col, "text": text}
            if formula is not None:
                cell["formula"] = formula
            cell.update(formula_meta)
            if cell_type != "n":
                cell["type"] = cell_type
            cells.append(cell)

        rows.append(cells)

    # Expand shared formulas
    all_formula_cells = [c for row_cells in rows for c in row_cells if "si" in c]
    if all_formula_cells:
        expand_shared_formulas(all_formula_cells)

    # Parse merge cells and mark shadow cells
    _apply_merge_cells(root, rows)

    return rows


def _apply_merge_cells(root: ET.Element, rows: list[list[Cell]]) -> None:
    """Parse <mergeCells> and mark anchor cells with colspan/rowspan,
    shadow cells with shadow=True (excluded from rendering)."""
    merge_cells = root.find(f"{{{NS_S}}}mergeCells")
    if merge_cells is None:
        return

    # Build coordinate → cell lookup
    cell_map: dict[tuple[int, int], Cell] = {}
    for row_cells in rows:
        for c in row_cells:
            cell_map[(c["col"], c["row"])] = c

    for mc in merge_cells.findall(f"{{{NS_S}}}mergeCell"):
        ref = mc.get("ref", "")
        if ":" not in ref:
            continue
        start_ref, end_ref = ref.split(":", 1)
        sc, sr = _parse_ref(start_ref)
        ec, er = _parse_ref(end_ref)

        anchor = cell_map.get((sc, sr))
        if anchor is not None:
            anchor["colspan"] = ec - sc + 1
            anchor["rowspan"] = er - sr + 1

        # Mark shadow cells
        for r in range(sr, er + 1):
            for c in range(sc, ec + 1):
                if c == sc and r == sr:
                    continue
                shadow = cell_map.get((c, r))
                if shadow is not None:
                    shadow["shadow"] = True


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
