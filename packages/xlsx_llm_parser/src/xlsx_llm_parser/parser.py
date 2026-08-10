"""XLSX parser — read workbook and worksheet data from an OPC package."""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.package import PackageReader

from ._sheet_post import (
    detect_pivot_tables,
    parse_drawings,
    parse_tables,
)
from .formats import parse_styles
from .models import (
    DefinedName,
    ParsedWorkbook,
    RichTextRun,
    SheetInfo,
)
from .worksheet import parse_sheet

# SpreadsheetML main namespace
NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Relationship types for sheet kind detection
_REL_WORKSHEET = f"{NS_R}/worksheet"
_REL_CHARTSHEET = f"{NS_R}/chartsheet"
_EXTERNAL_WORKBOOK_EXTENSIONS = (".xlsx", ".xlsm", ".xlsb", ".xls", ".xltx", ".xltm")


# OOXML cell type codes → LLM-readable semantic names.
def _parse_workbook(source: str | Path | bytes) -> ParsedWorkbook:
    """Parse an XLSX file and return a typed workbook IR."""
    limits = PackageLimits()
    with PackageReader(source, limits) as pkg:
        pkg.validate(required_part="xl/workbook.xml")

        date_1904, sheets, defined_names, external_links = _parse_workbook_xml(pkg)
        shared_strings, rich_text_map = _parse_shared_strings(pkg)
        fmt_index = parse_styles(pkg)
        fmt_index.set_date_system(date_1904)
        next_table_index = 0
        next_image_index = 1
        next_chart_index = 1
        next_pivot_index = 1

        for sheet in sheets:
            if sheet.get("kind") != "chartsheet":
                # Read sheet relationships once — shared across all helpers.
                sheet_rels = list(pkg.read_relationships_for_part(sheet["part"]))

                sheet_parse = parse_sheet(pkg, sheet["part"], shared_strings, rich_text_map, fmt_index, sheet_rels)
                sheet["rows"] = sheet_parse.rows
                if sheet_parse.hidden_cols:
                    sheet["hidden_cols"] = sheet_parse.hidden_cols
                if sheet_parse.sheet_protection:
                    sheet["sheet_protection"] = True
                if sheet_parse.filter_range:
                    sheet["filter_range"] = sheet_parse.filter_range
                if sheet_parse.filter_cols:
                    sheet["filter_cols"] = sheet_parse.filter_cols
                if sheet_parse.data_validations:
                    sheet["data_validations"] = sheet_parse.data_validations
                if sheet_parse.conditional_formats:
                    sheet["conditional_formats"] = sheet_parse.conditional_formats

                # Parse tables (ListObject) associated with this sheet
                tables = parse_tables(sheet_rels, pkg, start_index=next_table_index)
                next_table_index += len(tables)
                sheet["tables"] = tables

                # Parse drawing (images, shapes) + charts + pivots
                images, charts = parse_drawings(
                    sheet_rels,
                    pkg,
                    image_start=next_image_index,
                    chart_start=next_chart_index,
                )
                next_image_index += len(images)
                next_chart_index += len(charts)
                if images:
                    sheet["images"] = images
                if charts:
                    sheet["charts"] = charts
                pivots = detect_pivot_tables(sheet_rels, start_index=next_pivot_index)
                next_pivot_index += len(pivots)
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


def _parse_workbook_xml(
    pkg: PackageReader,
) -> tuple[bool, list[SheetInfo], list[DefinedName], list[str]]:
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
    rels = {rel.id: (rel.resolved_target, rel.type) for rel in pkg.read_relationships_for_part("xl/workbook.xml")}

    sheets: list[SheetInfo] = []
    sheets_elem = root.find(f"{{{NS_S}}}sheets")
    if sheets_elem is None:
        return date_1904, sheets, [], []

    for sheet_elem in sheets_elem.findall(f"{{{NS_S}}}sheet"):
        name = sheet_elem.get("name", "")
        rel_id = sheet_elem.get(f"{{{NS_R}}}id", "")
        rel_info = rels.get(rel_id)
        if rel_info is not None:
            part_candidate, rel_type = rel_info
            part = part_candidate or f"xl/worksheets/sheet{len(sheets) + 1}.xml"
        else:
            part = f"xl/worksheets/sheet{len(sheets) + 1}.xml"
            rel_type = _REL_WORKSHEET
        state = sheet_elem.get("state", "visible")

        kind = "chartsheet" if rel_type == _REL_CHARTSHEET else "worksheet"
        sheet_info: SheetInfo = {"name": name, "rows": [], "part": part, "kind": kind}
        if state != "visible":
            sheet_info["state"] = state
        sheets.append(sheet_info)

    # Defined names (global + sheet-scoped)
    defined_names: list[DefinedName] = []
    dn_elem = root.find(f"{{{NS_S}}}definedNames")
    if dn_elem is not None:
        for dn in dn_elem.findall(f"{{{NS_S}}}definedName"):
            name = dn.get("name", "")
            if not name:
                continue
            is_hidden = dn.get("hidden") == "1"
            scope_sheet_id_str = dn.get("localSheetId")
            scope_sheet = _scope_sheet_name(scope_sheet_id_str, sheets)
            defined_names.append(
                {
                    "name": name,
                    "ref": dn.text or "",
                    "scopeSheet": scope_sheet,
                    "hidden": is_hidden,
                }
            )

    # External references in defined names, excluding table structured references.
    external_links = _external_links_from_defined_names(defined_names)

    return date_1904, sheets, defined_names, external_links


def _scope_sheet_name(scope_sheet_id: str | None, sheets: list[SheetInfo]) -> str | None:
    if scope_sheet_id is None:
        return None
    try:
        sheet_index = int(scope_sheet_id)
    except ValueError:
        return None
    if 0 <= sheet_index < len(sheets):
        return sheets[sheet_index]["name"]
    return None


def _external_links_from_defined_names(defined_names: list[DefinedName]) -> list[str]:
    external_links: list[str] = []
    for defined_name in defined_names:
        for target in _external_link_targets(defined_name["ref"]):
            if target not in external_links:
                external_links.append(target)
    return external_links


def _external_link_targets(ref_text: str) -> list[str]:
    targets: list[str] = []
    for match in re.finditer(r"\[([^\]]+)\]", ref_text):
        target = match.group(1)
        suffix = ref_text[match.end() :]
        if _looks_like_external_reference(target, suffix):
            targets.append(target)
    return targets


def _looks_like_external_reference(target: str, suffix: str) -> bool:
    lower = target.lower()
    if lower.endswith(_EXTERNAL_WORKBOOK_EXTENSIONS):
        return True
    return target.isdigit() and "!" in suffix


def _parse_shared_strings(pkg: PackageReader) -> tuple[list[str], dict[int, list[RichTextRun]]]:
    """Parse xl/sharedStrings.xml into plain strings and rich-text run info.

    Returns (strings, rich_map) where rich_map maps SST index to formatted runs.
    """
    if not pkg.exists("xl/sharedStrings.xml"):
        return [], {}

    with pkg.open_entry("xl/sharedStrings.xml") as stream:
        root = ET.parse(stream).getroot()

    strings: list[str] = []
    rich_map: dict[int, list[RichTextRun]] = {}

    for idx, si in enumerate(root.findall(f"{{{NS_S}}}si")):
        t_elem = si.find(f"{{{NS_S}}}t")
        if t_elem is not None:
            strings.append(t_elem.text or "")
        else:
            texts: list[str] = []
            runs: list[RichTextRun] = []
            for r_elem in si.findall(f"{{{NS_S}}}r"):
                rt = r_elem.find(f"{{{NS_S}}}t")
                txt = rt.text if rt is not None and rt.text else ""
                texts.append(txt)
                rp = r_elem.find(f"{{{NS_S}}}rPr")
                if rp is not None:
                    run: RichTextRun = {"text": txt}
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
