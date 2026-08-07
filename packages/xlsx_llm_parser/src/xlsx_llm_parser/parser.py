"""XLSX parser — read workbook and worksheet data from an OPC package."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.package import PackageReader

from ._sheet_post import (
    apply_comments,
    apply_hyperlinks,
    apply_merge_cells,
    apply_spill_ranges,
    detect_pivot_tables,
    parse_drawings,
    parse_tables,
)
from ._utils import parse_ref
from .formats import FormatIndex, parse_styles
from .models import Cell, ParsedWorkbook, SheetInfo
from .share_formulas import expand_shared_formulas

# SpreadsheetML main namespace
NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Relationship types for sheet kind detection
_REL_WORKSHEET = f"{NS_R}/worksheet"
_REL_CHARTSHEET = f"{NS_R}/chartsheet"

# OOXML cell type codes → LLM-readable semantic names.
_CELL_TYPE_MAP: dict[str, str] = {
    "n": "number",
    "s": "string",
    "inlineStr": "string",
    "str": "string",
    "b": "boolean",
    "e": "error",
    "d": "date",
}


def _parse_workbook(source: str | Path | bytes) -> ParsedWorkbook:
    """Parse an XLSX file and return a typed workbook IR."""
    limits = PackageLimits()
    with PackageReader(source, limits) as pkg:
        pkg.validate(required_part="xl/workbook.xml")

        date_1904, sheets, defined_names, external_links = _parse_workbook_xml(pkg)
        sst, rich_map = _parse_shared_strings(pkg)
        fmt_index = parse_styles(pkg)
        fmt_index.set_date_system(date_1904)

        for sheet in sheets:
            if sheet.get("kind") != "chartsheet":
                # Read sheet relationships once — shared across all helpers.
                sheet_rels = list(pkg.read_relationships_for_part(sheet["part"]))

                (
                    rows,
                    hidden_cols,
                    sheet_protection,
                    filter_range,
                    filter_cols,
                    data_validations,
                    conditional_formats,
                ) = _parse_sheet(pkg, sheet["part"], sst, rich_map, fmt_index, sheet_rels)
                sheet["rows"] = rows
                if hidden_cols:
                    sheet["hidden_cols"] = hidden_cols
                if sheet_protection:
                    sheet["sheet_protection"] = True
                if filter_range:
                    sheet["filter_range"] = filter_range
                if filter_cols:
                    sheet["filter_cols"] = filter_cols
                if data_validations:
                    sheet["data_validations"] = data_validations
                if conditional_formats:
                    sheet["conditional_formats"] = conditional_formats

                # Parse tables (ListObject) associated with this sheet
                sheet["tables"] = parse_tables(sheet_rels, pkg)

                # Parse drawing (images, shapes) + charts + pivots
                images, charts = parse_drawings(sheet_rels, pkg)
                if images:
                    sheet["images"] = images
                if charts:
                    sheet["charts"] = charts
                pivots = detect_pivot_tables(sheet_rels)
                if pivots:
                    sheet["pivot_tables"] = pivots

    return {
        "sheets": sheets,
        "fmt_index": fmt_index,
        "metadata": {
            "source": str(source) if isinstance(source, (str, Path)) else "<bytes>",
            "defined_names": defined_names,
            "external_links": external_links,
        },
    }


def _parse_workbook_xml(pkg: PackageReader) -> tuple[bool, list[SheetInfo], list[dict], list[str]]:
    """Parse xl/workbook.xml for date system, sheet names, part targets,
    and defined names.

    Returns (date_1904, sheets, defined_names).
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
        return date_1904, sheets, [], []

    for sheet_elem in sheets_elem.findall(f"{{{NS_S}}}sheet"):
        name = sheet_elem.get("name", "")
        rel_id = sheet_elem.get(f"{{{NS_R}}}id", "")
        rel_info = rels.get(rel_id)
        part, rel_type = (
            rel_info
            if rel_info
            else (
                f"xl/worksheets/sheet{len(sheets) + 1}.xml",
                _REL_WORKSHEET,
            )
        )
        state = sheet_elem.get("state", "visible")

        kind = "chartsheet" if rel_type == _REL_CHARTSHEET else "worksheet"
        sheet_info: SheetInfo = {"name": name, "rows": [], "part": part, "kind": kind}
        if state != "visible":
            sheet_info["state"] = state
        sheets.append(sheet_info)

    # Defined names (global + sheet-scoped)
    defined_names: list[dict] = []
    dn_elem = root.find(f"{{{NS_S}}}definedNames")
    if dn_elem is not None:
        for dn in dn_elem.findall(f"{{{NS_S}}}definedName"):
            name = dn.get("name", "")
            if not name:
                continue
            is_hidden = dn.get("hidden") == "1"
            scope_sheet_id_str = dn.get("localSheetId")
            scope_sheet: str | None = None
            if scope_sheet_id_str is not None:
                try:
                    si = int(scope_sheet_id_str)
                    if 0 <= si < len(sheets):
                        scope_sheet = sheets[si]["name"]
                except ValueError:
                    pass
            defined_names.append(
                {
                    "name": name,
                    "ref": dn.text or "",
                    "scopeSheet": scope_sheet,
                    "hidden": is_hidden,
                }
            )

    # External references (D10: detect via defined names with [N] syntax)
    external_links: list[str] = []
    dn_elem2 = root.find(f"{{{NS_S}}}definedNames")
    if dn_elem2 is not None:
        for dn in dn_elem2.findall(f"{{{NS_S}}}definedName"):
            ref_text = dn.text or ""
            if "[" in ref_text:
                # Extract up to filename.xlsx] or filename.xlsm]
                import re

                m = re.search(r"\[([^\]]+)\]", ref_text)
                if m and m.group(1) not in external_links:
                    external_links.append(m.group(1))

    return date_1904, sheets, defined_names, external_links


def _parse_shared_strings(pkg: PackageReader) -> tuple[list[str], dict[int, list[dict]]]:
    """Parse xl/sharedStrings.xml into plain strings and rich-text run info.

    Returns (strings, rich_map) where rich_map maps SST index to formatted runs.
    """
    if not pkg.exists("xl/sharedStrings.xml"):
        return [], {}

    with pkg.open_entry("xl/sharedStrings.xml") as stream:
        root = ET.parse(stream).getroot()

    strings: list[str] = []
    rich_map: dict[int, list[dict]] = {}

    for idx, si in enumerate(root.findall(f"{{{NS_S}}}si")):
        t_elem = si.find(f"{{{NS_S}}}t")
        if t_elem is not None:
            strings.append(t_elem.text or "")
        else:
            texts: list[str] = []
            runs: list[dict] = []
            for r_elem in si.findall(f"{{{NS_S}}}r"):
                rt = r_elem.find(f"{{{NS_S}}}t")
                txt = rt.text if rt is not None and rt.text else ""
                texts.append(txt)
                rp = r_elem.find(f"{{{NS_S}}}rPr")
                if rp is not None:
                    run: dict = {"text": txt}
                    if rp.find(f"{{{NS_S}}}b") is not None:
                        run["bold"] = True
                    if rp.find(f"{{{NS_S}}}i") is not None:
                        run["italic"] = True
                    if rp.find(f"{{{NS_S}}}u") is not None:
                        run["underline"] = True
                    color = rp.find(f"{{{NS_S}}}color")
                    if color is not None:
                        rgb = color.get("rgb", "")
                        if rgb and rgb != "00000000":
                            run["color"] = f"#{rgb[2:]}" if len(rgb) == 8 else f"#{rgb}"
                    runs.append(run)
                else:
                    runs.append({"text": txt})
            strings.append("".join(texts))
            if any(len(r) > 1 for r in runs):  # has formatting beyond just text
                rich_map[idx] = runs

    return strings, rich_map


def _parse_sheet(
    pkg: PackageReader,
    part: str,
    sst: list[str],
    rich_map: dict[int, list[dict]] | None = None,
    fmt_index: FormatIndex | None = None,
    sheet_rels: list | None = None,
) -> tuple[list[list[Cell]], list[tuple[int, int]], bool, str, list[dict], list[dict], list[dict]]:
    """Parse a single worksheet XML into typed cell rows, hidden-col ranges,
    sheet-protection, filter, data validations, and conditional formats.

    *sheet_rels* are the pre-read relationships for this sheet part, shared
    across hyperlink, comment, table, drawing, and pivot helpers to avoid
    redundant I/O.
    """
    if not pkg.exists(part):
        return [], [], False, "", [], [], []

    with pkg.open_entry(part) as stream:
        root = ET.parse(stream).getroot()

    # Sheet protection (presence only — details stay in IR).
    sheet_protection = root.find(f"{{{NS_S}}}sheetProtection") is not None

    # AutoFilter (D7: range for structural, conditions for semantic).
    filter_range: str = ""
    filter_cols: list[dict] = []
    af = root.find(f"{{{NS_S}}}autoFilter")
    if af is not None:
        filter_range = af.get("ref", "")
        for fc in af.findall(f"{{{NS_S}}}filterColumn"):
            col_id_str = fc.get("colId", "0")
            filters = fc.find(f"{{{NS_S}}}filters")
            if filters is not None:
                vals = [
                    f.get("val", "") for f in filters.findall(f"{{{NS_S}}}filter") if f.get("val")
                ]
                if vals:
                    filter_cols.append({"col": int(col_id_str), "type": "values", "values": vals})

    # Data validations (D8).
    data_validations: list[dict] = []
    dvs = root.find(f"{{{NS_S}}}dataValidations")
    if dvs is not None:
        for dv in dvs.findall(f"{{{NS_S}}}dataValidation"):
            data_validations.append(
                {
                    "ranges": dv.get("sqref", ""),
                    "type": dv.get("type", ""),
                    "formula1": dv.findtext(f"{{{NS_S}}}formula1", ""),
                    "allowBlank": dv.get("allowBlank", "1") == "1",
                }
            )

    # Conditional formatting (D9).
    conditional_formats: list[dict] = []
    for cf in root.findall(f"{{{NS_S}}}conditionalFormatting"):
        cf_range = cf.get("sqref", "")
        for rule in cf.findall(f"{{{NS_S}}}cfRule"):
            conditional_formats.append(
                {
                    "ranges": cf_range,
                    "priority": int(rule.get("priority", "0")),
                    "ruleType": rule.get("type", ""),
                    "formula": rule.findtext(f"{{{NS_S}}}formula", ""),
                }
            )

    # Column definitions (hidden, width, outline) — parsed before sheetData.
    hidden_cols: list[tuple[int, int]] = []
    cols_elem = root.find(f"{{{NS_S}}}cols")
    if cols_elem is not None:
        for col_elem in cols_elem.findall(f"{{{NS_S}}}col"):
            if col_elem.get("hidden") == "1":
                cmin = int(col_elem.get("min", "1"))
                cmax = int(col_elem.get("max", cmin))
                hidden_cols.append((cmin, cmax))

    sheet_data = root.find(f"{{{NS_S}}}sheetData")
    if sheet_data is None:
        return (
            [],
            hidden_cols,
            sheet_protection,
            filter_range,
            filter_cols,
            data_validations,
            conditional_formats,
        )

    rows: list[list[Cell]] = []
    for row_elem in sheet_data.findall(f"{{{NS_S}}}row"):
        row_num = int(row_elem.get("r", "0"))
        row_hidden = row_elem.get("hidden") == "1"
        outline_level_str = row_elem.get("outlineLevel")
        outline_level = int(outline_level_str) if outline_level_str else 0
        collapsed = row_elem.get("collapsed") == "1"
        cells: list[Cell] = []
        for cell_elem in row_elem.findall(f"{{{NS_S}}}c"):
            ref = cell_elem.get("r", "")
            cell_type = cell_elem.get("t", "n")
            col, row = parse_ref(ref)

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
                            if rich_map is not None and idx in rich_map:
                                rich_runs = rich_map[idx]
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
            if row_hidden:
                cell["hidden"] = True
            if outline_level:
                cell["outlineLevel"] = outline_level
                if collapsed:
                    cell["collapsed"] = True
            # Attach rich text runs for semantic rendering
            if rich_map is not None and cell_type == "s" and v_elem is not None and v_elem.text:
                try:
                    idx = int(v_elem.text)
                    if idx in rich_map:
                        cell["rich"] = rich_map[idx]
                except ValueError:
                    pass
            # Store style index for semantic rendering
            style_str = cell_elem.get("s")
            if style_str is not None:
                cell["style"] = int(style_str)
            if formula is not None:
                cell["formula"] = formula
            cell.update(formula_meta)
            semantic_type = _CELL_TYPE_MAP.get(cell_type)
            if semantic_type and semantic_type != "number":
                cell["type"] = semantic_type
            cells.append(cell)

        rows.append(cells)

    # Expand shared formulas (needs only formula-bearing cells, not the full grid)
    all_formula_cells = [c for row_cells in rows for c in row_cells if "si" in c]
    if all_formula_cells:
        expand_shared_formulas(all_formula_cells)

    # Build (col, row) → Cell lookup once — shared by merge, spill,
    # hyperlink, and comment post-processing.
    cell_map: dict[tuple[int, int], Cell] = {}
    for row_cells in rows:
        for c in row_cells:
            cell_map[(c["col"], c["row"])] = c

    # Parse merge cells and mark shadow cells
    apply_merge_cells(root, cell_map)

    # Mark dynamic array spill relationships
    apply_spill_ranges(rows, cell_map)

    # Resolve hyperlinks (relationship IDs → URLs)
    apply_hyperlinks(root, cell_map, sheet_rels or [])

    # Attach legacy comments to cells
    apply_comments(cell_map, pkg, sheet_rels or [])

    return (
        rows,
        hidden_cols,
        sheet_protection,
        filter_range,
        filter_cols,
        data_validations,
        conditional_formats,
    )
