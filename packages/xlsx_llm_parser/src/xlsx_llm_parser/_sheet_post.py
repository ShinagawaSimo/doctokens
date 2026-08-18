"""Sheet post-processing — merge, spill, hyperlinks, comments, tables, drawings, pivots.

These functions operate on parsed cell rows and are called from ``_parse_sheet``.
They share a pre-built ``cell_map`` and pre-read sheet relationships to avoid
redundant iteration and I/O.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.chart_ml import parse_chart_xml
from ooxml_llm_core.models import RelationshipRecord
from ooxml_llm_core.package import PackageReader

from ._utils import col_letter, parse_ref
from .models import (
    Cell,
    ChartPoint,
    DrawingChart,
    DrawingChartSeries,
    DrawingImage,
    PivotTableInfo,
    TableInfo,
)

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

_REL_COMMENTS = f"{NS_R}/comments"
_REL_TABLE = f"{NS_R}/table"
_REL_DRAWING = f"{NS_R}/drawing"

NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


# ── Merge cells ──


def apply_merge_cells(root: ET.Element, cell_map: dict[tuple[int, int], Cell]) -> None:
    """Parse <mergeCells> and mark anchor cells with colspan/rowspan,
    shadow cells with shadow=True (excluded from rendering)."""
    merge_cells = root.find(f"{{{NS_S}}}mergeCells")
    if merge_cells is None:
        return

    for merge_cell in merge_cells.findall(f"{{{NS_S}}}mergeCell"):
        ref = merge_cell.get("ref", "")
        if ":" not in ref:
            continue
        start_ref, end_ref = ref.split(":", 1)
        start_col, start_row = parse_ref(start_ref)
        end_col, end_row = parse_ref(end_ref)

        anchor = cell_map.get((start_col, start_row))
        if anchor is not None:
            anchor["colspan"] = end_col - start_col + 1
            anchor["rowspan"] = end_row - start_row + 1

        # Mark shadow cells
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                if col == start_col and row == start_row:
                    continue
                shadow = cell_map.get((col, row))
                if shadow is not None:
                    shadow["shadow"] = True


# ── Dynamic array spill ──


def apply_spill_ranges(rows: list[list[Cell]], cell_map: dict[tuple[int, int], Cell]) -> None:
    """Detect dynamic-array spill ranges and mark source/recipient relationships.

    Only true dynamic-array formulas (``<f aca="1">``) are spill sources.
    Classic CSE array formulas share the ``t="array"``/``ref`` shape but do
    not spill.  Cells inside the range that carry no independent formula are
    marked as spill recipients pointing back to the source via ``spillFrom``.
    """
    sources = [cell for row_cells in rows for cell in row_cells if cell.get("formulaRange") and cell.get("dynamicArray")]
    apply_spill_sources(sources, cell_map)


def apply_spill_sources(sources: list[Cell], cell_map: dict[tuple[int, int], Cell]) -> None:
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
                recipient = cell_map.get((col, row))
                if recipient is not None and "formula" not in recipient and "si" not in recipient:
                    recipient["spillFrom"] = cell["ref"]


# ── Hyperlinks ──


def apply_hyperlinks(
    root: ET.Element,
    cell_map: dict[tuple[int, int], Cell],
    sheet_rels: list[RelationshipRecord],
) -> None:
    """Resolve <hyperlinks> via relationships and attach to cells."""
    hyperlinks = root.find(f"{{{NS_S}}}hyperlinks")
    if hyperlinks is None:
        return

    # Build rId → target from pre-read sheet rels
    rel_targets: dict[str, str] = {}
    for rel in sheet_rels:
        target = rel.resolved_target or ""
        if target:
            rel_targets[rel.id] = target

    for hyperlink in hyperlinks.findall(f"{{{NS_S}}}hyperlink"):
        ref = hyperlink.get("ref", "")
        location = hyperlink.get("location", "")
        relationship_id = hyperlink.get(f"{{{NS_R}}}id", "")

        col, row = parse_ref(ref)
        cell = cell_map.get((col, row))
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


# ── Comments ──


def apply_comments(
    cell_map: dict[tuple[int, int], Cell],
    pkg: PackageReader,
    sheet_rels: list[RelationshipRecord],
) -> None:
    """Parse legacy comments (xl/commentsN.xml) and attach to cells."""
    # Find comments part via pre-read sheet relationships
    comments_part: str | None = None
    for rel in sheet_rels:
        if rel.type == _REL_COMMENTS and rel.resolved_target:
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
        authors.extend(a.text or "" for a in authors_elem.findall(f"{{{NS_S}}}author"))

    comment_list = root.find(f"{{{NS_S}}}commentList")
    if comment_list is None:
        return
    for comment in comment_list.findall(f"{{{NS_S}}}comment"):
        ref = comment.get("ref", "")
        author_id_str = comment.get("authorId", "0")
        col, row = parse_ref(ref)
        cell = cell_map.get((col, row))
        if cell is None:
            continue
        try:
            author_id = int(author_id_str)
            cell["commentAuthor"] = authors[author_id] if author_id < len(authors) else ""
        except (ValueError, IndexError):
            cell["commentAuthor"] = ""
        text_elem = comment.find(f"{{{NS_S}}}text")
        if text_elem is not None:
            if text_elem.text:
                cell["comment"] = text_elem.text
            else:
                # Rich-text body: concatenate <r><t> runs
                parts: list[str] = []
                for run_element in text_elem.findall(f"{{{NS_S}}}r"):
                    text_run = run_element.find(f"{{{NS_S}}}t")
                    if text_run is not None and text_run.text:
                        parts.append(text_run.text)
                cell["comment"] = "".join(parts)
        else:
            cell["comment"] = ""


# ── Tables ──


def parse_tables(
    sheet_rels: list[RelationshipRecord],
    pkg: PackageReader,
    *,
    start_index: int = 0,
) -> list[TableInfo]:
    """Parse ListObject tables from pre-read *sheet_rels*."""
    tables: list[TableInfo] = []
    for rel in sheet_rels:
        if rel.type != _REL_TABLE:
            continue
        table_part = rel.resolved_target or ""
        if not table_part or not pkg.exists(table_part):
            continue
        with pkg.open_entry(table_part) as stream:
            root = ET.parse(stream).getroot()

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


# ── Drawings ──


def parse_drawings(
    sheet_rels: list[RelationshipRecord],
    pkg: PackageReader,
    *,
    image_start: int = 1,
    chart_start: int = 1,
) -> tuple[list[DrawingImage], list[DrawingChart]]:
    """Parse drawing anchors for images and chart references from pre-read *sheet_rels*."""
    images: list[DrawingImage] = []
    charts: list[DrawingChart] = []
    drawing_part: str | None = None
    for rel in sheet_rels:
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
        _parse_drawing_anchor(anchor, drawing_rels, images, charts, image_start, chart_start)
    for anchor in root.iter(f"{{{NS_XDR}}}oneCellAnchor"):
        _parse_drawing_anchor(anchor, drawing_rels, images, charts, image_start, chart_start)

    # Parse chart parts for richer metadata
    for chart in charts:
        if chart.get("part"):
            chart_data = _parse_chart_part(pkg, chart["part"])
            if chart_data.get("type"):
                chart["type"] = chart_data["type"]
            if chart_data.get("title"):
                chart["title"] = chart_data["title"]
            chart["series_count"] = chart_data.get("series_count", 0)
            if chart_data.get("series"):
                chart["series"] = chart_data["series"]

    return images, charts


def _parse_drawing_anchor(
    anchor: ET.Element,
    drawing_rels: dict[str, str],
    images: list[DrawingImage],
    charts: list[DrawingChart],
    image_start: int,
    chart_start: int,
) -> None:
    """Parse one drawing anchor for image/chart refs and position."""
    from_elem = anchor.find(f"{{{NS_XDR}}}from")
    if from_elem is None:
        return
    col = int(from_elem.findtext(f"{{{NS_XDR}}}col", "0"))
    row = int(from_elem.findtext(f"{{{NS_XDR}}}row", "0"))
    ref = f"{col_letter(col + 1)}{row + 1}"

    # Picture (image)
    for blip in anchor.iter(f"{{{NS_A}}}blip"):
        embed_id = blip.get(f"{{{NS_R}}}embed", "")
        target = drawing_rels.get(embed_id)
        if target:
            img_id = f"image{image_start + len(images)}"
            images.append({"id": img_id, "ref": ref, "alt": ""})
            break  # one image per anchor

    # Chart reference (namespace: drawingml/2006/chart, NOT spreadsheetDrawing)
    for chart_element in anchor.iter(f"{{{NS_C}}}chart"):
        chart_relationship_id = chart_element.get(f"{{{NS_R}}}id", "")
        chart_part = drawing_rels.get(chart_relationship_id, "")
        chart_id = f"chart{chart_start + len(charts)}"
        charts.append(
            {
                "id": chart_id,
                "ref": ref,
                "type": "",
                "title": "",
                "series_count": 0,
                "part": chart_part,
            }
        )


# ── Chart part parsing ──


def _parse_chart_part(pkg: PackageReader, chart_part: str) -> DrawingChart:
    """Parse a chart XML part via shared ChartML parser; return structured dict."""
    try:
        with pkg.open_entry(chart_part) as stream:
            root = ET.parse(stream).getroot()
        chart_info = parse_chart_xml(root)
    except Exception:
        return {"type": "", "title": "", "series_count": 0}

    series_list: list[DrawingChartSeries] = []
    for source_series in chart_info.get("series", []):
        point_count = max(len(source_series.get("categories", [])), len(source_series.get("values", [])))
        series_item: DrawingChartSeries = {
            "index": source_series["index"],
            "pointCount": point_count,
        }
        if source_series.get("name"):
            series_item["name"] = source_series["name"]
        if "min" in source_series:
            series_item["min"] = source_series["min"]
        if "max" in source_series:
            series_item["max"] = source_series["max"]
        # Full data points
        categories = source_series.get("categories", [])
        values = source_series.get("values", [])
        points: list[ChartPoint] = []
        for index in range(max(len(categories), len(values))):
            point: ChartPoint = {}
            if index < len(categories):
                point["category"] = categories[index]
            if index < len(values):
                point["value"] = values[index]
            if point:
                points.append(point)
        if points:
            series_item["points"] = points
        series_list.append(series_item)

    return {
        "type": chart_info.get("chart_type", ""),
        "title": chart_info.get("title", ""),
        "series_count": chart_info.get("series_count", 0),
        "series": series_list,
    }


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
