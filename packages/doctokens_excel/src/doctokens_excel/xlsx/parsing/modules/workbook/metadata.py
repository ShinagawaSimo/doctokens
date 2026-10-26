"""Metadata."""

from __future__ import annotations

import re

from doctokens_core.containers.opc.reader import PackageReader

from ....model.workbook import DefinedName, SheetInfo
from .shared_strings import _parse_shared_strings as _parse_shared_strings

# SpreadsheetML main namespace
NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


# Relationship types for sheet kind detection
_REL_WORKSHEET = f"{NS_R}/worksheet"


_REL_CHARTSHEET = f"{NS_R}/chartsheet"


_EXTERNAL_WORKBOOK_EXTENSIONS = (".xlsx", ".xlsm", ".xlsb", ".xls", ".xltx", ".xltm")


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
    date_1904 = workbook_properties is not None and workbook_properties.get("date1904", "").lower() in {
        "1",
        "true",
        "on",
    }

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
