"""XLSX parser — read workbook and worksheet data from an OPC package."""

from __future__ import annotations

import re
from pathlib import Path

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.metrics import MetricsRecorder
from ooxml_llm_core.models import ParseReport, ParseWarning
from ooxml_llm_core.package import PackageReader

from ._sheet_post import (
    parse_drawings,
    parse_tables,
    parse_threaded_comment_people,
)
from .features import CellControlCatalog, PivotCatalog, RichValueCatalog
from .formats import parse_styles
from .models import (
    DefinedName,
    ParsedWorkbook,
    ParseOptions,
    RichTextRun,
    SheetInfo,
)
from .plan import XlsxFeature, XlsxParsePlan
from .worksheet import parse_sheet

# SpreadsheetML main namespace
NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Relationship types for sheet kind detection
_REL_WORKSHEET = f"{NS_R}/worksheet"
_REL_CHARTSHEET = f"{NS_R}/chartsheet"
_EXTERNAL_WORKBOOK_EXTENSIONS = (".xlsx", ".xlsm", ".xlsb", ".xls", ".xltx", ".xltm")


# OOXML cell type codes -> LLM-readable semantic names.
def _parse_workbook(
    source: str | Path | bytes,
    options: ParseOptions | None = None,
    *,
    plan: XlsxParsePlan | None = None,
) -> ParsedWorkbook:
    """Parse an XLSX file and return a typed workbook IR."""
    parse_options = options or ParseOptions()
    parse_plan = plan or XlsxParsePlan.session()
    limits = PackageLimits(
        max_zip_entries=parse_options.max_zip_entries,
        max_entry_uncompressed_bytes=parse_options.max_entry_uncompressed_bytes,
        max_total_uncompressed_bytes=parse_options.max_total_uncompressed_bytes,
    )
    metrics = MetricsRecorder()
    warnings: list[ParseWarning] = []
    with metrics.stage("parse"), PackageReader(source, limits) as package_reader:
        package_reader.validate(required_part="xl/workbook.xml")

        date_1904, worksheet_infos, defined_names, external_links = _parse_workbook_xml(
            package_reader,
            include_defined_names=parse_plan.needs(XlsxFeature.DEFINED_NAMES),
            include_external_links=parse_plan.needs(XlsxFeature.EXTERNAL_LINKS),
        )
        if parse_plan.sheet_names is not None:
            worksheet_infos = [sheet_info for sheet_info in worksheet_infos if sheet_info["name"] in parse_plan.sheet_names]
        shared_strings, rich_text_map = _parse_shared_strings(
            package_reader,
            include_rich_text=parse_plan.needs(XlsxFeature.RICH_TEXT),
        )
        rich_values = (
            RichValueCatalog.from_package(package_reader) if parse_plan.needs(XlsxFeature.RICH_VALUES) else RichValueCatalog()
        )
        cell_controls = (
            CellControlCatalog.from_package(package_reader)
            if parse_plan.needs(XlsxFeature.CELL_CONTROLS)
            else CellControlCatalog()
        )
        pivot_catalog = PivotCatalog.from_package(package_reader) if parse_plan.needs(XlsxFeature.PIVOTS) else PivotCatalog()
        format_index = parse_styles(
            package_reader,
            include_semantic_details=parse_plan.needs(XlsxFeature.SEMANTIC_STYLES),
        )
        format_index.set_cell_controls(cell_controls.by_style)
        format_index.set_date_system(date_1904)
        threaded_comment_people = parse_threaded_comment_people(package_reader) if parse_plan.needs(XlsxFeature.COMMENTS) else {}
        next_table_index = 0
        next_image_index = 1
        next_chart_index = 1
        next_pivot_index = 1

        for sheet_info in worksheet_infos:
            if sheet_info.get("kind") != "chartsheet":
                # Read sheet relationships once — shared across all helpers.
                sheet_relationships = list(package_reader.read_relationships_for_part(sheet_info["part"]))

                sheet_result = parse_sheet(
                    package_reader,
                    sheet_info["part"],
                    shared_strings,
                    rich_text_map,
                    format_index,
                    sheet_relationships,
                    threaded_comment_people,
                    rich_values,
                    plan=parse_plan,
                    cell_window=parse_plan.cell_window,
                )
                sheet_info["rows"] = sheet_result.rows
                if sheet_result.hidden_cols:
                    sheet_info["hidden_cols"] = sheet_result.hidden_cols
                if sheet_result.sheet_protection:
                    sheet_info["sheet_protection"] = True
                if sheet_result.filter_range:
                    sheet_info["filter_range"] = sheet_result.filter_range
                if sheet_result.filter_cols:
                    sheet_info["filter_cols"] = sheet_result.filter_cols
                if sheet_result.data_validations:
                    sheet_info["data_validations"] = sheet_result.data_validations
                if sheet_result.conditional_formats:
                    sheet_info["conditional_formats"] = sheet_result.conditional_formats

                # Parse tables (ListObject) associated with this sheet
                tables = (
                    parse_tables(sheet_relationships, package_reader, start_index=next_table_index)
                    if parse_plan.needs(XlsxFeature.TABLES)
                    else []
                )
                next_table_index += len(tables)
                sheet_info["tables"] = tables

                # Parse drawing (images, shapes) + charts + pivots
                images, charts = (
                    parse_drawings(
                        sheet_relationships,
                        package_reader,
                        image_start=next_image_index,
                        chart_start=next_chart_index,
                    )
                    if parse_plan.needs(XlsxFeature.DRAWINGS)
                    else ([], [])
                )
                next_image_index += len(images)
                next_chart_index += len(charts)
                if images:
                    sheet_info["images"] = images
                if charts:
                    sheet_info["charts"] = charts
                pivots = (
                    pivot_catalog.tables_for_relationships(sheet_relationships, start_index=next_pivot_index)
                    if parse_plan.needs(XlsxFeature.PIVOTS)
                    else []
                )
                next_pivot_index += len(pivots)
                if pivots:
                    sheet_info["pivot_tables"] = pivots

    workbook_manifest: dict[str, object] = {
        "sheetCount": len(worksheet_infos),
        "cellCount": sum(len(row) for sheet in worksheet_infos for row in sheet.get("rows", [])),
        "tableCount": sum(len(sheet.get("tables", [])) for sheet in worksheet_infos),
        "imageCount": sum(len(sheet.get("images", [])) for sheet in worksheet_infos),
        "chartCount": sum(len(sheet.get("charts", [])) for sheet in worksheet_infos),
        "pivotTableCount": sum(len(sheet.get("pivot_tables", [])) for sheet in worksheet_infos),
    }
    metrics.set_counter("sheetCount", len(worksheet_infos))
    metrics.set_counter("cellCount", workbook_manifest["cellCount"] if isinstance(workbook_manifest["cellCount"], int) else 0)
    metrics.set_counter("tableCount", workbook_manifest["tableCount"] if isinstance(workbook_manifest["tableCount"], int) else 0)
    metrics.set_counter("imageCount", workbook_manifest["imageCount"] if isinstance(workbook_manifest["imageCount"], int) else 0)
    metrics.set_counter("chartCount", workbook_manifest["chartCount"] if isinstance(workbook_manifest["chartCount"], int) else 0)
    metrics.set_counter(
        "pivotTableCount",
        workbook_manifest["pivotTableCount"] if isinstance(workbook_manifest["pivotTableCount"], int) else 0,
    )
    report = ParseReport("xlsx", 1, workbook_manifest, tuple(warnings), metrics.snapshot())
    return {
        "sheets": worksheet_infos,
        "fmt_index": format_index,
        "metadata": {
            "source": str(source) if isinstance(source, (str, Path)) else "<bytes>",
            "defined_names": defined_names,
            "external_links": external_links,
            "pivot_caches": pivot_catalog.caches,
            "slicers": pivot_catalog.slicers,
            "timelines": pivot_catalog.timelines,
        },
        "report": report,
    }


def _parse_workbook_xml(
    package_reader: PackageReader,
    *,
    include_defined_names: bool,
    include_external_links: bool,
) -> tuple[bool, list[SheetInfo], list[DefinedName], list[str]]:
    """Parse xl/workbook.xml for date system, sheet names, part targets,
    and defined names.

    Returns the date system, sheet metadata, defined names, and external links.
    """
    workbook_root = package_reader.read_xml("xl/workbook.xml")

    # Date system: 1900 (default) or 1904 (Mac)
    workbook_properties = workbook_root.find(f"{{{NS_S}}}workbookPr")
    date_1904 = workbook_properties is not None and workbook_properties.get("date1904") == "1"

    # Build a lookup of rel_id → (resolved_target, rel_type)
    workbook_relationships = {
        relationship.id: (relationship.resolved_target, relationship.type)
        for relationship in package_reader.read_relationships_for_part("xl/workbook.xml")
    }

    sheet_infos: list[SheetInfo] = []
    sheets_element = workbook_root.find(f"{{{NS_S}}}sheets")
    if sheets_element is None:
        return date_1904, sheet_infos, [], []

    for sheet_element in sheets_element.findall(f"{{{NS_S}}}sheet"):
        sheet_name = sheet_element.get("name", "")
        relationship_id = sheet_element.get(f"{{{NS_R}}}id", "")
        relationship_info = workbook_relationships.get(relationship_id)
        if relationship_info is not None:
            part_candidate, relationship_type = relationship_info
            part = part_candidate or f"xl/worksheets/sheet{len(sheet_infos) + 1}.xml"
        else:
            part = f"xl/worksheets/sheet{len(sheet_infos) + 1}.xml"
            relationship_type = _REL_WORKSHEET
        visibility_state = sheet_element.get("state", "visible")

        sheet_kind = "chartsheet" if relationship_type == _REL_CHARTSHEET else "worksheet"
        sheet_info: SheetInfo = {"name": sheet_name, "rows": [], "part": part, "kind": sheet_kind}
        if visibility_state != "visible":
            sheet_info["state"] = visibility_state
        sheet_infos.append(sheet_info)

    # Defined names (global + sheet-scoped)
    defined_names: list[DefinedName] = []
    defined_names_element = workbook_root.find(f"{{{NS_S}}}definedNames")
    if include_defined_names and defined_names_element is not None:
        for defined_name_element in defined_names_element.findall(f"{{{NS_S}}}definedName"):
            defined_name = defined_name_element.get("name", "")
            if not defined_name:
                continue
            is_hidden = defined_name_element.get("hidden") == "1"
            scope_sheet_id_str = defined_name_element.get("localSheetId")
            scope_sheet = _scope_sheet_name(scope_sheet_id_str, sheet_infos)
            defined_names.append(
                {
                    "name": defined_name,
                    "ref": defined_name_element.text or "",
                    "scopeSheet": scope_sheet,
                    "hidden": is_hidden,
                }
            )

    # External references in defined names, excluding table structured references.
    external_links = _external_links_from_defined_names(defined_names) if include_external_links else []

    return date_1904, sheet_infos, defined_names, external_links


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
        if _looks_like_external_reference(target):
            targets.append(target)
    return targets


def _looks_like_external_reference(target: str) -> bool:
    return target.lower().endswith(_EXTERNAL_WORKBOOK_EXTENSIONS)


def _parse_shared_strings(
    package_reader: PackageReader,
    *,
    include_rich_text: bool,
) -> tuple[list[str], dict[int, list[RichTextRun]]]:
    """Parse xl/sharedStrings.xml into plain strings and rich-text run info.

    Returns (strings, rich_map) where rich_map maps SST index to formatted runs.
    """
    if not package_reader.exists("xl/sharedStrings.xml"):
        return [], {}

    shared_strings_root = package_reader.read_xml("xl/sharedStrings.xml")

    strings: list[str] = []
    rich_map: dict[int, list[RichTextRun]] = {}

    for shared_string_index, shared_string_element in enumerate(shared_strings_root.findall(f"{{{NS_S}}}si")):
        text_element = shared_string_element.find(f"{{{NS_S}}}t")
        if text_element is not None:
            strings.append(text_element.text or "")
        else:
            text_parts: list[str] = []
            rich_text_runs: list[RichTextRun] = []
            for run_element in shared_string_element.findall(f"{{{NS_S}}}r"):
                run_text_element = run_element.find(f"{{{NS_S}}}t")
                run_text = run_text_element.text if run_text_element is not None and run_text_element.text else ""
                text_parts.append(run_text)
                run_properties = run_element.find(f"{{{NS_S}}}rPr") if include_rich_text else None
                if run_properties is not None:
                    rich_text_run: RichTextRun = {"text": run_text}
                    if run_properties.find(f"{{{NS_S}}}b") is not None:
                        rich_text_run["bold"] = True
                    if run_properties.find(f"{{{NS_S}}}i") is not None:
                        rich_text_run["italic"] = True
                    if run_properties.find(f"{{{NS_S}}}u") is not None:
                        rich_text_run["underline"] = True
                    color = run_properties.find(f"{{{NS_S}}}color")
                    if color is not None:
                        rgb = color.get("rgb", "")
                        if rgb and rgb != "00000000":
                            rich_text_run["color"] = f"#{rgb[2:]}" if len(rgb) == 8 else f"#{rgb}"
                    rich_text_runs.append(rich_text_run)
                else:
                    rich_text_runs.append({"text": run_text})
            strings.append("".join(text_parts))
            if include_rich_text and any(len(run) > 1 for run in rich_text_runs):
                rich_map[shared_string_index] = rich_text_runs

    return strings, rich_map
