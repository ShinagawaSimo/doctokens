"""Search."""

from __future__ import annotations

import re
from html import escape as escape_text

from .models import Cell, ParsedWorkbook, SheetInfo
from .rendering.selection import find_sheet


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
    if not query:
        return "<matches>\n"
    pattern = re.compile(re.escape(query))
    matches: list[str] = []
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
                    matches.append(f"<match field=definedName>{escape_text(name)} = {escape_text(defined_name['ref'])}")
    return "<matches>\n" + "\n".join(matches) + "\n"


def _cell_match(sheet_name: str, cell: Cell, pattern: re.Pattern[str], kind: str | None) -> str | None:
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
            cell_ref = f"{escape_text(sheet_name, quote=True)}!{cell['ref']}"
            return f'<match cell="{cell_ref}" field={field_name}>{escape_text(rendered)}'
    return None
