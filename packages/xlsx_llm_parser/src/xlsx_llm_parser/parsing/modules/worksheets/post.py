"""Sheet post-processing — merge, spill, hyperlinks, comments, tables, drawings, pivots.

These functions operate on parsed cell rows and are called from ``_parse_sheet``.
They share a pre-built ``cell_map`` and pre-read sheet relationships to avoid
redundant iteration and I/O.
"""

from __future__ import annotations

from collections.abc import Iterable
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning, RelationshipRecord
from ooxml_llm_core.package import PackageReader

from ...._utils import coord_key, parse_ref
from ....models import (
    Cell,
    PivotTableInfo,
    TableInfo,
)
from .post_common import NS_R, NS_S, _ensure_cell, _warn

_REL_TABLE = f"{NS_R}/table"


# ── Merge cells ──


def apply_merge_refs(merge_refs: Iterable[str], cell_map: dict[int, Cell]) -> None:
    """Apply already-scanned merge ranges to the compact cell coordinate map."""
    for ref in merge_refs:
        if ":" not in ref:
            continue
        start_ref, end_ref = ref.split(":", 1)
        start_col, start_row = parse_ref(start_ref)
        end_col, end_row = parse_ref(end_ref)

        anchor = cell_map.get(coord_key(start_col, start_row))
        if anchor is not None:
            anchor["colspan"] = end_col - start_col + 1
            anchor["rowspan"] = end_row - start_row + 1

        # Mark shadow cells
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                if col == start_col and row == start_row:
                    continue
                shadow = cell_map.get(coord_key(col, row))
                if shadow is not None:
                    shadow["shadow"] = True


# ── Dynamic array spill ──


def apply_spill_sources(sources: list[Cell], cell_map: dict[int, Cell]) -> None:
    """Apply spill relationships for a pre-collected source list."""
    for cell in sources:
        formula_range = cell.get("formulaRange")
        if not formula_range or ":" not in formula_range:
            continue
        start_ref, end_ref = formula_range.split(":", 1)
        start_col, start_row = parse_ref(start_ref)
        end_col, end_row = parse_ref(end_ref)

        # Skip if the range covers only the cell itself
        spills_only_to_source = (
            start_col == cell["col"] and start_row == cell["row"] and end_col == cell["col"] and end_row == cell["row"]
        )
        if spills_only_to_source:
            continue

        cell["spillRange"] = formula_range

        # Mark spill recipients: cells inside the range without their own formula
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                if col == cell["col"] and row == cell["row"]:
                    continue
                recipient = cell_map.get(coord_key(col, row))
                if recipient is not None and "formula" not in recipient and "si" not in recipient:
                    recipient["spillFrom"] = cell["ref"]


# ── Hyperlinks ──


def apply_hyperlink_specs(
    specs: Iterable[tuple[str, str, str]],
    cell_map: dict[int, Cell],
    sheet_rels: list[RelationshipRecord],
    rows: list[list[Cell]] | None = None,
    rows_by_number: dict[int, list[Cell]] | None = None,
) -> None:
    """Resolve scanned hyperlink declarations via relationships."""
    rel_targets: dict[str, str] = {}
    for rel in sheet_rels:
        target = rel.resolved_target or ""
        if target:
            rel_targets[rel.id] = target

    for ref, relationship_id, location in specs:
        if not ref:
            continue
        col, row = parse_ref(ref)
        cell = _ensure_cell(cell_map, rows, rows_by_number, ref, col, row)
        if cell is None:
            continue

        # External URL takes precedence; fallback to internal location.
        link_target = rel_targets.get(relationship_id) if relationship_id else None
        if link_target:
            if location:
                cell["hyperlink"] = f"{link_target}#{location}"
            else:
                cell["hyperlink"] = link_target
        elif location:
            cell["hyperlink"] = f"#{location}"


# ── Tables ──


def parse_tables(
    sheet_rels: list[RelationshipRecord],
    pkg: PackageReader,
    *,
    start_index: int = 0,
    warnings: list[ParseWarning] | None = None,
) -> list[TableInfo]:
    """Parse ListObject tables from pre-read *sheet_rels*."""
    tables: list[TableInfo] = []
    for rel in sheet_rels:
        if rel.type != _REL_TABLE:
            continue
        table_part = rel.resolved_target or ""
        if not table_part or not pkg.exists(table_part):
            _warn(warnings, "TABLE_PART_MISSING", "Referenced table part is missing", f"{rel.source_part}#{rel.id}")
            continue
        try:
            root = pkg.read_xml(table_part)
        except ET.ParseError as exc:
            _warn(warnings, "TABLE_XML_INVALID", f"Invalid table XML: {exc}", table_part)
            continue

        name = root.get("displayName", root.get("name", ""))
        ref = root.get("ref", "")
        table_id = f"table-{start_index + len(tables)}"
        columns: list[str] = []
        try:
            totals_row = int(root.get("totalsRowCount", "0")) >= 1
        except ValueError:
            totals_row = False
        table_cols = root.find(f"{{{NS_S}}}tableColumns")
        if table_cols is not None:
            for table_column in table_cols.findall(f"{{{NS_S}}}tableColumn"):
                column_name = table_column.get("name", "")
                if column_name:
                    columns.append(column_name)
        tables.append(
            {
                "id": table_id,
                "name": name,
                "ref": ref,
                "columns": columns,
                "totalsRow": totals_row,
            }
        )
    return tables


# ── Pivot tables ──


def detect_pivot_tables(
    sheet_rels: list[RelationshipRecord],
    *,
    start_index: int = 1,
) -> list[PivotTableInfo]:
    """Detect pivot table relationships from pre-read *sheet_rels*."""
    pivots: list[PivotTableInfo] = []
    for rel in sheet_rels:
        if rel.type == f"{NS_R}/pivotTable":
            pivots.append({"id": f"pivot{start_index + len(pivots)}", "ref": "", "name": ""})
    return pivots
