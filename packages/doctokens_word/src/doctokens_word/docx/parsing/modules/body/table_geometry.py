"""Selected table rows/cells, logical grid positions, and vertical merge origins."""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from ....model import ContentControl, ParseWarning, TableCell, TableRow, append_warning
from ....ooxml.namespaces import attr, first_child, is_on, local_name
from ....ooxml.property_changes import retained_revision, selected_properties, structural_revision
from ....ooxml.wrapped_content import content_children


def grid_number(properties: ET.Element | None, name: str, warnings: list[ParseWarning], part: str, default: int = 0) -> int:
    value = attr(first_child(properties, "w", name), "w", "val")
    if value is None:
        return default
    try:
        result = int(value)
        if result < default:
            raise ValueError
        return result
    except ValueError:
        append_warning(
            warnings,
            "INVALID_GRID_SPAN" if name == "gridSpan" else "INVALID_TABLE_GRID_OFFSET",
            f"Invalid {name}: {value!r}",
            part=part,
        )
        return default


@dataclass
class CellSource:
    node: ET.Element
    properties: ET.Element | None
    controls: tuple[ContentControl, ...]
    column: int
    span: int


@dataclass
class RowSource:
    node: ET.Element
    properties: ET.Element | None
    controls: tuple[ContentControl, ...]
    cells: list[CellSource]
    before: int
    after: int
    header: bool

    @property
    def width(self) -> int:
        return self.before + sum(cell.span for cell in self.cells) + self.after


def table_rows(table: ET.Element, view: str, warnings: list[ParseWarning], part: str, maximum_columns: int) -> list[RowSource]:
    rows: list[RowSource] = []
    grid = selected_properties(first_child(table, "w", "tblGrid"), view)
    if grid is not None and sum(local_name(child.tag) == "gridCol" for child in grid) > maximum_columns:
        raise ValueError(f"DOCX table exceeds max_table_columns={maximum_columns}")
    for node, controls in content_children(table):
        if local_name(node.tag) != "tr":
            continue
        current = first_child(node, "w", "trPr")
        if not retained_revision(structural_revision(current), view):
            continue
        properties = selected_properties(current, view)
        before = grid_number(properties, "gridBefore", warnings, part)
        after = grid_number(properties, "gridAfter", warnings, part)
        if before + after > maximum_columns:
            raise ValueError(f"DOCX table exceeds max_table_columns={maximum_columns}")
        column = before
        cells: list[CellSource] = []
        for child, cell_controls in content_children(node):
            if local_name(child.tag) != "tc":
                continue
            cell_pr = first_child(child, "w", "tcPr")
            if not retained_revision(structural_revision(cell_pr), view):
                continue
            selected = selected_properties(cell_pr, view)
            span = grid_number(selected, "gridSpan", warnings, part, default=1)
            if column + span + after > maximum_columns:
                raise ValueError(f"DOCX table exceeds max_table_columns={maximum_columns}")
            cells.append(CellSource(child, selected, cell_controls, column, span))
            column += span
        header = first_child(properties, "w", "tblHeader")
        rows.append(RowSource(node, properties, controls, cells, before, after, header is not None and is_on(header)))
    return rows


def vertical_merge(properties: ET.Element | None, view: str) -> str | None:
    change = first_child(properties, "w", "cellMerge")
    if change is not None:
        value = attr(change, "w", "vMergeOrig" if view == "original" else "vMerge")
        if value is not None:
            return {"rest": "restart", "cont": "continue"}.get(value, value) or None
    node = first_child(properties, "w", "vMerge")
    return (attr(node, "w", "val") or "continue") if node is not None else None


def apply_vertical_merges(rows: list[TableRow], active: dict[int, TableCell]) -> None:
    for row in rows:
        occupied: set[int] = set()
        for cell in row["cells"]:
            columns = range(cell["colIndex"], cell["colIndex"] + cell["colSpan"])
            occupied.update(columns)
            if cell.get("vMerge") == "restart":
                for column in columns:
                    active[column] = cell
            elif cell.get("vMerge") == "continue":
                origins: list[TableCell] = []
                for column in columns:
                    origin = active.get(column)
                    if origin is not None and all(origin is not existing for existing in origins):
                        origins.append(origin)
                for origin in origins:
                    origin["rowSpan"] += 1
            else:
                for column in columns:
                    active.pop(column, None)
        for column in list(active):
            if column not in occupied:
                active.pop(column, None)
