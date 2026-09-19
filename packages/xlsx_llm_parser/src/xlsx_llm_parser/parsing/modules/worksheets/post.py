"""Sheet post-processing — merge, spill, hyperlinks, comments, tables, drawings, pivots.

These functions operate on parsed cell rows and are called from ``_parse_sheet``.
They share a pre-built ``cell_map`` and pre-read sheet relationships to avoid
redundant iteration and I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from xml.etree import ElementTree as ET

from ooxml_llm_core.annotations import AnnotationMention, valid_parent_links
from ooxml_llm_core.chart_ml import CHART_RELATIONSHIP_TYPES, parse_chart_xml
from ooxml_llm_core.models import RelationshipRecord
from ooxml_llm_core.package import PackageReader
from ooxml_llm_core.xml import local_name

from ...._utils import col_letter, coord_key, parse_ref
from ....models import (
    Cell,
    ChartPoint,
    DrawingChart,
    DrawingChartSeries,
    DrawingImage,
    PivotTableInfo,
    TableInfo,
    ThreadedComment,
)

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

_REL_COMMENTS = f"{NS_R}/comments"
_REL_THREADED_COMMENTS = "http://schemas.microsoft.com/office/2017/10/relationships/threadedComment"
_REL_TABLE = f"{NS_R}/table"
_REL_DRAWING = f"{NS_R}/drawing"

NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


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


# ── Comments ──


def apply_comments(
    cell_map: dict[int, Cell],
    pkg: PackageReader,
    sheet_rels: list[RelationshipRecord],
    rows: list[list[Cell]] | None = None,
    rows_by_number: dict[int, list[Cell]] | None = None,
    threaded_comment_people: Mapping[str, str] | None = None,
) -> None:
    """Parse legacy and threaded comments, keeping each collaboration thread on its cell."""
    # Find comments part via pre-read sheet relationships
    comments_part: str | None = None
    for rel in sheet_rels:
        if rel.type == _REL_COMMENTS and rel.resolved_target:
            comments_part = rel.resolved_target
            break
    if comments_part is not None and pkg.exists(comments_part):
        try:
            root = pkg.read_xml(comments_part)
        except ET.ParseError:
            root = None
        if root is not None:
            _apply_legacy_comments(root, cell_map, rows, rows_by_number)

    _apply_threaded_comments(cell_map, pkg, sheet_rels, rows, rows_by_number, threaded_comment_people or {})


def _apply_legacy_comments(
    root: ET.Element,
    cell_map: dict[int, Cell],
    rows: list[list[Cell]] | None,
    rows_by_number: dict[int, list[Cell]] | None,
) -> None:
    """Attach legacy note-style comments while leaving threaded comments independent."""
    authors: list[str] = []
    authors_elem = root.find(f"{{{NS_S}}}authors")
    if authors_elem is not None:
        authors.extend(a.text or "" for a in authors_elem.findall(f"{{{NS_S}}}author"))
    comment_list = root.find(f"{{{NS_S}}}commentList")
    if comment_list is None:
        return
    for comment in comment_list.findall(f"{{{NS_S}}}comment"):
        ref = comment.get("ref", "")
        try:
            col, row = parse_ref(ref)
        except ValueError:
            continue
        cell = _ensure_cell(cell_map, rows, rows_by_number, ref, col, row)
        if cell is None:
            continue
        author_id_str = comment.get("authorId", "0")
        try:
            author_id = int(author_id_str)
            cell["commentAuthor"] = authors[author_id] if author_id < len(authors) else ""
        except (ValueError, IndexError):
            cell["commentAuthor"] = ""
        text_elem = comment.find(f"{{{NS_S}}}text")
        if text_elem is None:
            cell["comment"] = ""
        else:
            cell["comment"] = "".join(text_elem.itertext())


def parse_threaded_comment_people(pkg: PackageReader) -> dict[str, str]:
    """Read the workbook-wide people catalog once for modern comment authors and mentions."""
    part = "xl/persons/person.xml"
    if not pkg.exists(part):
        return {}
    try:
        root = pkg.read_xml(part)
    except ET.ParseError:
        return {}
    people: dict[str, str] = {}
    for element in root.iter():
        if local_name(element.tag) != "person":
            continue
        person_id = element.get("id")
        display_name = element.get("displayName")
        if person_id and display_name:
            people[person_id] = display_name
    return people


def _apply_threaded_comments(
    cell_map: dict[int, Cell],
    pkg: PackageReader,
    sheet_rels: list[RelationshipRecord],
    rows: list[list[Cell]] | None,
    rows_by_number: dict[int, list[Cell]] | None,
    people: Mapping[str, str],
) -> None:
    """Attach one modern comment conversation to its target cell without a package-wide scan."""
    part = next(
        (
            rel.resolved_target
            for rel in sheet_rels
            if rel.type == _REL_THREADED_COMMENTS and rel.resolved_target and pkg.exists(rel.resolved_target)
        ),
        None,
    )
    if part is None:
        return
    try:
        root = pkg.read_xml(part)
    except ET.ParseError:
        return

    pending: list[tuple[ThreadedComment, str, str | None]] = []
    raw_to_display: dict[str, str] = {}
    per_cell_index: dict[str, int] = {}
    for element in root:
        if local_name(element.tag) != "threadedComment":
            continue
        ref = element.get("ref", "")
        try:
            col, row = parse_ref(ref)
        except ValueError:
            continue
        cell = _ensure_cell(cell_map, rows, rows_by_number, ref, col, row)
        if cell is None:
            continue
        ordinal = per_cell_index.get(ref, 0) + 1
        per_cell_index[ref] = ordinal
        item: ThreadedComment = {"id": f"thread-{ref}-{ordinal}", "text": _threaded_comment_text(element)}
        author = people.get(element.get("personId", ""), "")
        if author:
            item["author"] = author
        date = element.get("dT")
        if date:
            item["date"] = date
        if _as_bool(element.get("done")):
            item["resolved"] = True
        mentions = _threaded_mentions(element, people)
        if mentions:
            item["mentions"] = mentions
        raw_id = element.get("id") or item["id"]
        raw_to_display[raw_id] = item["id"]
        pending.append((item, raw_id, element.get("parentId")))
        cell.setdefault("threadedComments", []).append(item)

    links, _dangling = valid_parent_links((raw_id, parent_id) for _item, raw_id, parent_id in pending)
    for item, raw_id, _parent_id in pending:
        parent_raw_id = links.get(raw_id)
        if parent_raw_id:
            item["parentId"] = raw_to_display[parent_raw_id]


def _threaded_comment_text(element: ET.Element) -> str:
    text_node = next((child for child in element if local_name(child.tag) == "text"), None)
    return "".join(text_node.itertext()) if text_node is not None else ""


def _threaded_mentions(element: ET.Element, people: Mapping[str, str]) -> list[AnnotationMention]:
    mentions: list[AnnotationMention] = []
    for descendant in element.iter():
        if local_name(descendant.tag) != "mention":
            continue
        person = people.get(descendant.get("personId", ""), "")
        if not person:
            continue
        mention: AnnotationMention = {"person": person}
        start = _safe_int(descendant.get("startIndex"))
        length = _safe_int(descendant.get("length"))
        if start is not None:
            mention["start"] = start
        if length is not None:
            mention["length"] = length
        mentions.append(mention)
    return mentions


def _ensure_cell(
    cell_map: dict[int, Cell],
    rows: list[list[Cell]] | None,
    rows_by_number: dict[int, list[Cell]] | None,
    ref: str,
    col: int,
    row: int,
) -> Cell | None:
    """Materialize an otherwise empty annotated/navigable cell so its semantics remain visible."""
    existing = cell_map.get(coord_key(col, row))
    if existing is not None:
        return existing
    if rows is None:
        return None
    cell: Cell = {"ref": ref, "col": col, "row": row, "text": ""}
    cell_map[coord_key(col, row)] = cell
    target_row = rows_by_number.get(row) if rows_by_number is not None else None
    if target_row is None:
        target_row = [cell]
        rows.append(target_row)
        if rows_by_number is not None:
            rows_by_number[row] = target_row
    else:
        target_row.append(cell)
    return cell


def _as_bool(value: str | None) -> bool:
    return value is not None and value.lower() not in {"0", "false", "off", "none"}


def _safe_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


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
        root = pkg.read_xml(table_part)

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
    drawing_rels: dict[str, RelationshipRecord] = {}
    for rel in pkg.read_relationships_for_part(drawing_part):
        drawing_rels[rel.id] = rel

    root = pkg.read_xml(drawing_part)

    for anchor_name in ("twoCellAnchor", "oneCellAnchor", "absoluteAnchor"):
        for anchor in root.iter(f"{{{NS_XDR}}}{anchor_name}"):
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
            if "plotTypes" in chart_data:
                chart["plotTypes"] = chart_data["plotTypes"]

    return images, charts


def _parse_drawing_anchor(
    anchor: ET.Element,
    drawing_rels: dict[str, RelationshipRecord],
    images: list[DrawingImage],
    charts: list[DrawingChart],
    image_start: int,
    chart_start: int,
) -> None:
    """Parse one drawing anchor for image/chart refs and position."""
    from_elem = anchor.find(f"{{{NS_XDR}}}from")
    if from_elem is None:
        ref = ""
    else:
        col = int(from_elem.findtext(f"{{{NS_XDR}}}col", "0"))
        row = int(from_elem.findtext(f"{{{NS_XDR}}}row", "0"))
        ref = f"{col_letter(col + 1)}{row + 1}"

    # Picture (image)
    for blip in anchor.iter(f"{{{NS_A}}}blip"):
        embed_id = blip.get(f"{{{NS_R}}}embed", "")
        target = drawing_rels.get(embed_id)
        if target is not None and target.resolved_target:
            img_id = f"image{image_start + len(images)}"
            images.append({"id": img_id, "ref": ref, "alt": "", "part": target.resolved_target})
            break  # one image per anchor

    # Chart reference (namespace: drawingml/2006/chart, NOT spreadsheetDrawing)
    for chart_element in anchor.iter():
        if _local_name(chart_element.tag) != "chart":
            continue
        chart_relationship_id = chart_element.get(f"{{{NS_R}}}id", "")
        chart_rel = drawing_rels.get(chart_relationship_id)
        if chart_rel is None or chart_rel.type not in CHART_RELATIONSHIP_TYPES:
            continue
        chart_part = chart_rel.resolved_target or ""
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
        root = pkg.read_xml(chart_part)
        chart_info = parse_chart_xml(root)
    except Exception:
        return {"type": "", "title": "", "series_count": 0}

    series_list: list[DrawingChartSeries] = []
    for source_series in chart_info.get("series", []):
        point_count = max(
            len(source_series.get("categories", [])),
            len(source_series.get("values", [])),
            len(source_series.get("x_values", [])),
            len(source_series.get("y_values", [])),
            len(source_series.get("bubble_sizes", [])),
        )
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
        if "plot_index" in source_series:
            series_item["plotIndex"] = source_series["plot_index"]
        if "chart_type" in source_series:
            series_item["chartType"] = source_series["chart_type"]
        if source_series.get("x_values"):
            series_item["xValues"] = source_series["x_values"]
        if source_series.get("y_values"):
            series_item["yValues"] = source_series["y_values"]
        if source_series.get("bubble_sizes"):
            series_item["bubbleSizes"] = source_series["bubble_sizes"]
        if source_series.get("hidden"):
            series_item["hidden"] = True
        # Full data points
        categories = source_series.get("categories", [])
        values = source_series.get("values", [])
        x_values = source_series.get("x_values", [])
        y_values = source_series.get("y_values", [])
        bubble_sizes = source_series.get("bubble_sizes", [])
        points: list[ChartPoint] = []
        for index in range(point_count):
            point: ChartPoint = {}
            if index < len(categories):
                point["category"] = categories[index]
            if index < len(values):
                point["value"] = values[index]
            if index < len(x_values):
                point["x"] = x_values[index]
            if index < len(y_values):
                point["y"] = y_values[index]
            if index < len(bubble_sizes):
                point["bubbleSize"] = bubble_sizes[index]
            if point:
                points.append(point)
        if points:
            series_item["points"] = points
        series_list.append(series_item)

    result: DrawingChart = {
        "type": chart_info.get("chart_type", ""),
        "title": chart_info.get("title", ""),
        "series_count": chart_info.get("series_count", 0),
        "series": series_list,
    }
    plot_types = [plot.get("chart_type", "unknown") for plot in chart_info.get("plots", [])]
    if chart_info.get("chart_type") == "combination" and plot_types:
        result["plotTypes"] = plot_types
    return result


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


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
