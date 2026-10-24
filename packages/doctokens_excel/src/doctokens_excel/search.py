"""Search."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from doctokens_core.doctokens_xml import append, element, serialize
from doctokens_core.models import ParseResult
from doctokens_core.resource_xml import operation_root

from ._api_support import Source, _result
from .models import Cell, ParsedWorkbook, ParseOptions, SheetInfo
from .parsing.runner import _parse_workbook
from .plan import XlsxParsePlan
from .rendering.selection import find_sheet


def find_xlsx_cells(
    source: Source,
    query: str,
    *,
    options: ParseOptions | None = None,
    sheets: list[str] | None = None,
    kind: str | None = None,
    limit: int = 50,
) -> ParseResult:
    workbook = _parse_workbook(source, options, plan=XlsxParsePlan.search(kind, sheets))
    return _result(
        workbook, _find_cells(workbook, query, sheets=sheets, kind=kind, limit=limit), "structural", {"kind": "search"}
    )


def _sheet(workbook: ParsedWorkbook, name: str) -> SheetInfo:
    try:
        return find_sheet(workbook, name)
    except ValueError as exc:
        raise KeyError(name) from exc


def _find_cells(
    workbook: ParsedWorkbook,
    query: str,
    *,
    sheets: list[str] | None,
    kind: str | None,
    limit: int,
) -> str:
    root = operation_root("xlsx", "structural")
    container = append(root, "matches")
    if not query:
        return serialize(root)
    pattern = re.compile(re.escape(query))
    matches: list[ET.Element] = []
    selected_sheets = sheets or [sheet["name"] for sheet in workbook["sheets"]]
    seen_names: set[str] = set()
    for sheet_name in selected_sheets:
        if len(matches) >= limit:
            break
        sheet = _sheet(workbook, sheet_name)
        for row in sheet.get("rows", []):
            for cell in row:
                if len(matches) >= limit:
                    break
                match = _cell_match(sheet_name, cell, pattern, kind)
                if match is not None:
                    matches.append(match)
        if len(matches) < limit and kind in {None, "definedName"}:
            for defined_name in workbook["metadata"].get("defined_names", []):
                if len(matches) >= limit:
                    break
                name = defined_name["name"]
                if name in seen_names:
                    continue
                scope = defined_name.get("scopeSheet")
                if scope and scope != sheet_name:
                    continue
                if pattern.search(name) or pattern.search(defined_name.get("ref", "")):
                    seen_names.add(name)
                    matches.append(element("match", f"{name} = {defined_name['ref']}", field="definedName"))
    container.extend(matches)
    return serialize(root)


def _cell_match(sheet_name: str, cell: Cell, pattern: re.Pattern[str], kind: str | None) -> ET.Element | None:
    fields = (
        ("value", cell["text"]),
        ("formula", cell.get("formula", "")),
        ("comment", cell.get("comment", "")),
        ("hyperlink", cell.get("hyperlink", "")),
    )
    for field_name, value in fields:
        if kind not in {None, field_name}:
            continue
        rendered = str(value)
        if pattern.search(rendered):
            cell_ref = f"{sheet_name}!{cell['ref']}"
            return element("match", rendered, cell=cell_ref, field=field_name)
    return None
