"""DrawingML table content and merge structure."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from ....model.presentation import LayoutContext, ShapeBlock, TableCell
from ....ooxml.namespaces import first_child, local_name
from ....ooxml.run_format import drawingml_bool as _drawingml_bool
from ....ooxml.text_styles import TextStyleParser
from .lists import integer as _parse_int
from .shape_details import _find_descendant, _shape_name
from .text import DrawingTextParser


class TableParser:
    """Own table numbering and retain the text parser's complete paragraphs."""

    def __init__(self, warnings: list[ParseWarning], text_parser: DrawingTextParser, *, include_formatting: bool) -> None:
        self._warnings = warnings
        self._text_parser = text_parser
        self._styles = TextStyleParser({}, warnings, include_formatting=include_formatting)
        self._table_index = 0

    def parse(self, frame: ET.Element, part: str, ordinal: int, context: LayoutContext) -> ShapeBlock | None:
        tbl = _find_descendant(frame, "tbl")
        if tbl is None:
            self._warnings.append(
                ParseWarning(code="TABLE_MISSING_TBL", message="graphicFrame table without a:tbl", locator=part)
            )
            return None
        rows: list[list[str]] = []
        table_cells: list[list[TableCell]] = []
        column_widths: list[int] = []
        grid = first_child(tbl, "a", "tblGrid")
        if grid is not None:
            for column in grid:
                if local_name(column.tag) == "gridCol":
                    width = _parse_int(column.get("w"), 0)
                    if width > 0:
                        column_widths.append(width)
        for child in tbl:
            if local_name(child.tag) != "tr":
                continue
            row: list[str] = []
            cell_row: list[TableCell] = []
            for cell in child:
                if local_name(cell.tag) != "tc":
                    continue
                tx_body = first_child(cell, "a", "txBody")
                list_style = first_child(tx_body, "a", "lstStyle") if tx_body is not None else None
                inherited = (
                    self._styles.paragraph_defaults(list_style, context["color_map"], theme=context["theme"])
                    if list_style is not None
                    else None
                )
                result = self._text_parser.parse(
                    tx_body, part=part, theme=context["theme"], color_map=context["color_map"], inherited_styles=inherited
                )
                text = result.text or ""
                source_paragraphs = []
                for paragraph in result.paragraphs:
                    source_runs = paragraph.get("runs", [])
                    if paragraph.get("bullet") or paragraph.get("numberType"):
                        source_runs = source_runs[1:]
                    source_paragraphs.append(
                        "".join("\ufffc" if run.get("unparsed") else run.get("text", "") for run in source_runs)
                    )
                row.append(text)
                cell_info: TableCell = {"text": text, "searchParagraphs": source_paragraphs}
                if result.paragraphs:
                    cell_info["paragraphs"] = result.paragraphs
                col_span = _parse_int(cell.get("gridSpan"), 1)
                row_span = _parse_int(cell.get("rowSpan"), 1)
                if col_span > 1:
                    cell_info["colSpan"] = col_span
                if row_span > 1:
                    cell_info["rowSpan"] = row_span
                if _drawingml_bool(cell.get("hMerge")):
                    cell_info["hMerge"] = True
                if _drawingml_bool(cell.get("vMerge")):
                    cell_info["vMerge"] = True
                cell_row.append(cell_info)
            rows.append(row)
            table_cells.append(cell_row)
        self._normalize_table_merges(table_cells)
        self._table_index += 1
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "table",
            "name": _shape_name(frame) or "",
            "rows": rows,
            "tableId": f"table{self._table_index}",
        }
        shape["tableCells"] = table_cells
        if column_widths:
            shape["columnWidths"] = column_widths
        return shape

    @staticmethod
    def _normalize_table_merges(rows: list[list[TableCell]]) -> None:
        """Infer spans when producers emit only hMerge/vMerge continuations."""
        explicit_row_spans = {id(cell) for row in rows for cell in row if "rowSpan" in cell}
        for row in rows:
            anchor: TableCell | None = None
            explicit_col_span = False
            for cell in row:
                if cell.get("hMerge"):
                    if anchor is not None and not explicit_col_span:
                        anchor["colSpan"] = anchor.get("colSpan", 1) + 1
                else:
                    anchor = cell
                    explicit_col_span = "colSpan" in cell
        for row_index, row in enumerate(rows):
            for column_index, cell in enumerate(row):
                if not cell.get("vMerge"):
                    continue
                for previous_index in range(row_index - 1, -1, -1):
                    previous_row = rows[previous_index]
                    if column_index >= len(previous_row):
                        continue
                    anchor = previous_row[column_index]
                    if anchor.get("vMerge"):
                        continue
                    if id(anchor) not in explicit_row_spans:
                        anchor["rowSpan"] = row_index - previous_index + 1
                    break
