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
                (rows, hidden_cols, sheet_protection,
                 filter_range, filter_cols,
                 data_validations, conditional_formats) = _parse_sheet(
                    pkg, sheet["part"], sst, rich_map, fmt_index
                )
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
                sheet["tables"] = _parse_tables(pkg, sheet["part"])

                # Parse drawing (images, shapes) + charts + pivots
                images, charts = _parse_drawings(pkg, sheet["part"])
                if images:
                    sheet["images"] = images
                if charts:
                    sheet["charts"] = charts
                pivots = _detect_pivot_tables(pkg, sheet["part"])
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


def _parse_workbook_xml(pkg: PackageReader) -> tuple[bool, list[SheetInfo]]:
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
            defined_names.append({
                "name": name,
                "ref": dn.text or "",
                "scopeSheet": scope_sheet,
                "hidden": is_hidden,
            })

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
    pkg: PackageReader, part: str, sst: list[str],
    rich_map: dict[int, list[dict]] | None = None,
    fmt_index: FormatIndex | None = None,
) -> tuple[list[list[Cell]], list[tuple[int, int]], bool, str, list[dict]]:
    """Parse a single worksheet XML into typed cell rows, hidden-col ranges,
    sheet-protection, filter, data validations, and conditional formats."""
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
                vals = [f.get("val", "") for f in filters.findall(f"{{{NS_S}}}filter") if f.get("val")]
                if vals:
                    filter_cols.append({"col": int(col_id_str), "type": "values", "values": vals})

    # Data validations (D8).
    data_validations: list[dict] = []
    dvs = root.find(f"{{{NS_S}}}dataValidations")
    if dvs is not None:
        for dv in dvs.findall(f"{{{NS_S}}}dataValidation"):
            data_validations.append({
                "ranges": dv.get("sqref", ""),
                "type": dv.get("type", ""),
                "formula1": dv.findtext(f"{{{NS_S}}}formula1", ""),
                "allowBlank": dv.get("allowBlank", "1") == "1",
            })

    # Conditional formatting (D9).
    conditional_formats: list[dict] = []
    for cf in root.findall(f"{{{NS_S}}}conditionalFormatting"):
        cf_range = cf.get("sqref", "")
        for rule in cf.findall(f"{{{NS_S}}}cfRule"):
            conditional_formats.append({
                "ranges": cf_range,
                "priority": int(rule.get("priority", "0")),
                "ruleType": rule.get("type", ""),
                "formula": rule.findtext(f"{{{NS_S}}}formula", ""),
            })

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
        return [], hidden_cols, sheet_protection, filter_range, filter_cols, data_validations, conditional_formats

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

    # Expand shared formulas
    all_formula_cells = [c for row_cells in rows for c in row_cells if "si" in c]
    if all_formula_cells:
        expand_shared_formulas(all_formula_cells)

    # Parse merge cells and mark shadow cells
    _apply_merge_cells(root, rows)

    # Mark dynamic array spill relationships
    _apply_spill_ranges(rows)

    # Resolve hyperlinks (relationship IDs → URLs)
    _apply_hyperlinks(root, rows, pkg, part)

    # Attach legacy comments to cells
    _apply_comments(rows, pkg, part)

    return rows, hidden_cols, sheet_protection, filter_range, filter_cols, data_validations, conditional_formats


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


def _apply_spill_ranges(rows: list[list[Cell]]) -> None:
    """Detect dynamic-array spill ranges and mark source/recipient relationships.

    An array formula with a ``ref`` range larger than its own cell is a spill
    source.  Cells inside that range that carry no independent formula are
    marked as spill recipients pointing back to the source via ``spillFrom``.
    """
    # Build coordinate → cell lookup
    cell_map: dict[tuple[int, int], Cell] = {}
    for row_cells in rows:
        for c in row_cells:
            cell_map[(c["col"], c["row"])] = c

    for row_cells in rows:
        for cell in row_cells:
            formula_range = cell.get("formulaRange")
            if not formula_range:
                continue
            if ":" not in formula_range:
                continue
            start_ref, end_ref = formula_range.split(":", 1)
            sc, sr = _parse_ref(start_ref)
            ec, er = _parse_ref(end_ref)

            # Skip if the range covers only the cell itself
            if sc == cell["col"] and sr == cell["row"] and ec == cell["col"] and er == cell["row"]:
                continue

            cell["spillRange"] = formula_range

            # Mark spill recipients: cells inside the range without their own formula
            for r in range(sr, er + 1):
                for col in range(sc, ec + 1):
                    if col == cell["col"] and r == cell["row"]:
                        continue
                    recipient = cell_map.get((col, r))
                    if recipient is not None and "formula" not in recipient and "si" not in recipient:
                        recipient["spillFrom"] = cell["ref"]


def _apply_hyperlinks(root: ET.Element, rows: list[list[Cell]],
                     pkg: PackageReader, part: str) -> None:
    """Resolve <hyperlinks> via relationships and attach to cells."""
    hyperlinks = root.find(f"{{{NS_S}}}hyperlinks")
    if hyperlinks is None:
        return

    # Build rId → (target, target_mode) from sheet rels
    rel_targets: dict[str, str] = {}
    for rel in pkg.read_relationships_for_part(part):
        target = rel.resolved_target or ""
        if target:
            rel_targets[rel.id] = target

    # Build coordinate → cell lookup
    cell_map: dict[tuple[int, int], Cell] = {}
    for row_cells in rows:
        for c in row_cells:
            cell_map[(c["col"], c["row"])] = c

    for hl in hyperlinks.findall(f"{{{NS_S}}}hyperlink"):
        ref = hl.get("ref", "")
        location = hl.get("location", "")
        r_id = hl.get(f"{{{NS_R}}}id", "")

        col, row = _parse_ref(ref)
        cell = cell_map.get((col, row))
        if cell is None:
            continue

        # External URL takes precedence; fallback to internal location.
        target = rel_targets.get(r_id) if r_id else None
        if target:
            if location:
                # External link with internal location fragment
                cell["hyperlink"] = f"{target}#{location}"
            else:
                cell["hyperlink"] = target
        elif location:
            cell["hyperlink"] = f"#{location}"


_REL_COMMENTS = f"{NS_R}/comments"
_REL_TABLE = f"{NS_R}/table"
_REL_DRAWING = f"{NS_R}/drawing"
_REL_IMAGE = f"{NS_R}/image"
_REL_CHART = f"{NS_R}/chart"

NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _apply_comments(rows: list[list[Cell]], pkg: PackageReader, sheet_part: str) -> None:
    """Parse legacy comments (xl/commentsN.xml) and attach to cells."""
    # Find comments part via sheet relationships
    comments_part: str | None = None
    for rel in pkg.read_relationships_for_part(sheet_part):
        if rel.type == _REL_COMMENTS:
            comments_part = rel.resolved_target
            break
    if comments_part is None or not pkg.exists(comments_part):
        return

    with pkg.open_entry(comments_part) as stream:
        root = ET.parse(stream).getroot()

    # Authors list
    authors: list[str] = []
    authors_elem = root.find(f"{{{NS_S}}}authors")
    if authors_elem is not None:
        for a in authors_elem.findall(f"{{{NS_S}}}author"):
            authors.append(a.text or "")

    # Build cell lookup
    cell_map: dict[tuple[int, int], Cell] = {}
    for row_cells in rows:
        for c in row_cells:
            cell_map[(c["col"], c["row"])] = c

    comment_list = root.find(f"{{{NS_S}}}commentList")
    if comment_list is None:
        return
    idx = 0
    for cmt in comment_list.findall(f"{{{NS_S}}}comment"):
        ref = cmt.get("ref", "")
        author_id_str = cmt.get("authorId", "0")
        col, row = _parse_ref(ref)
        cell = cell_map.get((col, row))
        if cell is None:
            idx += 1
            continue
        try:
            author_id = int(author_id_str)
            cell["commentAuthor"] = authors[author_id] if author_id < len(authors) else ""
        except (ValueError, IndexError):
            cell["commentAuthor"] = ""
        text_elem = cmt.find(f"{{{NS_S}}}text")
        cell["comment"] = text_elem.text if text_elem is not None and text_elem.text else ""
        idx += 1


def _parse_tables(pkg: PackageReader, sheet_part: str) -> list[dict]:
    """Parse ListObject tables associated with *sheet_part*."""
    tables: list[dict] = []
    for rel in pkg.read_relationships_for_part(sheet_part):
        if rel.type != _REL_TABLE:
            continue
        table_part = rel.resolved_target or ""
        if not table_part or not pkg.exists(table_part):
            continue
        with pkg.open_entry(table_part) as stream:
            root = ET.parse(stream).getroot()

        name = root.get("displayName", root.get("name", ""))
        ref = root.get("ref", "")
        table_id = f"table-{len(tables)}"
        columns: list[str] = []
        totals_row = root.get("totalsRowCount", "0") == "1"
        table_cols = root.find(f"{{{NS_S}}}tableColumns")
        if table_cols is not None:
            for tc in table_cols.findall(f"{{{NS_S}}}tableColumn"):
                col_name = tc.get("name", "")
                if col_name:
                    columns.append(col_name)
        tables.append({
            "id": table_id,
            "name": name,
            "ref": ref,
            "columns": columns,
            "totalsRow": totals_row,
        })
    return tables


def _parse_drawings(pkg: PackageReader, sheet_part: str) -> tuple[list[dict], list[dict]]:
    """Parse drawing anchors for images and chart references."""
    images: list[dict] = []
    charts: list[dict] = []
    drawing_part: str | None = None
    for rel in pkg.read_relationships_for_part(sheet_part):
        if rel.type == _REL_DRAWING:
            drawing_part = rel.resolved_target
            break
    if not drawing_part or not pkg.exists(drawing_part):
        return images, charts

    # Drawing relationships for image/chart media
    drawing_rels: dict[str, str] = {}
    for rel in pkg.read_relationships_for_part(drawing_part):
        drawing_rels[rel.id] = rel.resolved_target or ""

    with pkg.open_entry(drawing_part) as stream:
        root = ET.parse(stream).getroot()

    for anchor in root.iter(f"{{{NS_XDR}}}twoCellAnchor"):
        _parse_drawing_anchor(anchor, drawing_rels, images, charts)
    for anchor in root.iter(f"{{{NS_XDR}}}oneCellAnchor"):
        _parse_drawing_anchor(anchor, drawing_rels, images, charts)

    return images, charts


def _parse_drawing_anchor(anchor: ET.Element, drawing_rels: dict[str, str],
                          images: list[dict], charts: list[dict]) -> None:
    """Parse one drawing anchor for image/chart refs and position."""
    from_elem = anchor.find(f"{{{NS_XDR}}}from")
    if from_elem is None:
        return
    col = int(from_elem.findtext(f"{{{NS_XDR}}}col", "0"))
    row = int(from_elem.findtext(f"{{{NS_XDR}}}row", "0"))
    ref = f"{_str_from_col(col + 1)}{row + 1}"

    # Picture (image)
    for blip in anchor.iter(f"{{{NS_A}}}blip"):
        embed_id = blip.get(f"{{{NS_R}}}embed", "")
        target = drawing_rels.get(embed_id)
        if target:
            img_id = f"image{len(images) + 1}"
            images.append({"id": img_id, "ref": ref, "alt": ""})
            break  # one image per anchor

    # Chart reference
    for chart_elem in anchor.iter(f"{{{NS_XDR}}}chart"):
        chart_id = len(charts) + 1
        charts.append({"id": f"chart{chart_id}", "ref": ref, "type": "", "title": "", "series_count": 0})


def _detect_pivot_tables(pkg: PackageReader, sheet_part: str) -> list[dict]:
    """Detect pivot table relationships for a sheet."""
    pivots: list[dict] = []
    for rel in pkg.read_relationships_for_part(sheet_part):
        if rel.type == f"{NS_R}/pivotTable":
            pivots.append({"id": f"pivot{len(pivots) + 1}", "ref": "", "name": ""})
    return pivots


def _str_from_col(c: int) -> str:
    result = ""
    while c > 0:
        c, rem = divmod(c - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


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
