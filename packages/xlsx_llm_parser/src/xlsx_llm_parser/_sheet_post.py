"""Sheet post-processing — merge, spill, hyperlinks, comments, tables, drawings, pivots.

These functions operate on parsed cell rows and are called from ``_parse_sheet``.
They share a pre-built ``cell_map`` and pre-read sheet relationships to avoid
redundant iteration and I/O.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.chart_ml import parse_chart_xml
from ooxml_llm_core.package import PackageReader

from ._utils import col_letter, parse_ref
from .models import Cell

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

    for mc in merge_cells.findall(f"{{{NS_S}}}mergeCell"):
        ref = mc.get("ref", "")
        if ":" not in ref:
            continue
        start_ref, end_ref = ref.split(":", 1)
        sc, sr = parse_ref(start_ref)
        ec, er = parse_ref(end_ref)

        anchor = cell_map.get((sc, sr))
        if anchor is not None:
            anchor["colspan"] = ec - sc + 1
            anchor["rowspan"] = er - sr + 1

        # Mark shadow cells
        for r in range(sr, er + 1):
            for c in range(sc, ec + 1):
                if c == sc and r == sr:
                    continue
                shadow = cell_map.get((c, r))
                if shadow is not None:
                    shadow["shadow"] = True


# ── Dynamic array spill ──


def apply_spill_ranges(rows: list[list[Cell]],
                       cell_map: dict[tuple[int, int], Cell]) -> None:
    """Detect dynamic-array spill ranges and mark source/recipient relationships.

    An array formula with a ``ref`` range larger than its own cell is a spill
    source.  Cells inside that range that carry no independent formula are
    marked as spill recipients pointing back to the source via ``spillFrom``.
    """
    for row_cells in rows:
        for cell in row_cells:
            formula_range = cell.get("formulaRange")
            if not formula_range:
                continue
            if ":" not in formula_range:
                continue
            start_ref, end_ref = formula_range.split(":", 1)
            sc, sr = parse_ref(start_ref)
            ec, er = parse_ref(end_ref)

            # Skip if the range covers only the cell itself
            if sc == cell["col"] and sr == cell["row"] and ec == cell["col"] and er == cell["row"]:
                continue

            cell["spillRange"] = formula_range

            # Mark spill recipients: cells inside the range without their own formula
            for r in range(sr, er + 1):
                for col in range(sc, ec + 1):
                    if col == cell["col"] and r == cell["row"]:
                        continue
                    recipient = cell_map.get((col, r))
                    if recipient is not None and "formula" not in recipient and "si" not in recipient:
                        recipient["spillFrom"] = cell["ref"]


# ── Hyperlinks ──


def apply_hyperlinks(root: ET.Element, cell_map: dict[tuple[int, int], Cell],
                     sheet_rels: list) -> None:
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

    for hl in hyperlinks.findall(f"{{{NS_S}}}hyperlink"):
        ref = hl.get("ref", "")
        location = hl.get("location", "")
        r_id = hl.get(f"{{{NS_R}}}id", "")

        col, row = parse_ref(ref)
        cell = cell_map.get((col, row))
        if cell is None:
            continue

        # External URL takes precedence; fallback to internal location.
        target = rel_targets.get(r_id) if r_id else None
        if target:
            if location:
                cell["hyperlink"] = f"{target}#{location}"
            else:
                cell["hyperlink"] = target
        elif location:
            cell["hyperlink"] = f"#{location}"


# ── Comments ──


def apply_comments(cell_map: dict[tuple[int, int], Cell],
                   pkg: PackageReader, sheet_rels: list) -> None:
    """Parse legacy comments (xl/commentsN.xml) and attach to cells."""
    # Find comments part via pre-read sheet relationships
    comments_part: str | None = None
    for rel in sheet_rels:
        if rel.type == _REL_COMMENTS:
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
        for a in authors_elem.findall(f"{{{NS_S}}}author"):
            authors.append(a.text or "")

    comment_list = root.find(f"{{{NS_S}}}commentList")
    if comment_list is None:
        return
    for cmt in comment_list.findall(f"{{{NS_S}}}comment"):
        ref = cmt.get("ref", "")
        author_id_str = cmt.get("authorId", "0")
        col, row = parse_ref(ref)
        cell = cell_map.get((col, row))
        if cell is None:
            continue
        try:
            author_id = int(author_id_str)
            cell["commentAuthor"] = authors[author_id] if author_id < len(authors) else ""
        except (ValueError, IndexError):
            cell["commentAuthor"] = ""
        text_elem = cmt.find(f"{{{NS_S}}}text")
        if text_elem is not None:
            if text_elem.text:
                cell["comment"] = text_elem.text
            else:
                # Rich-text body: concatenate <r><t> runs
                parts = []
                for r_elem in text_elem.findall(f"{{{NS_S}}}r"):
                    t = r_elem.find(f"{{{NS_S}}}t")
                    if t is not None and t.text:
                        parts.append(t.text)
                cell["comment"] = "".join(parts)
        else:
            cell["comment"] = ""


# ── Tables ──


def parse_tables(sheet_rels: list, pkg: PackageReader) -> list[dict]:
    """Parse ListObject tables from pre-read *sheet_rels*."""
    tables: list[dict] = []
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
        table_id = f"table-{len(tables)}"
        columns: list[str] = []
        totals_row = root.get("totalsRowCount", "0") == "1"
        table_cols = root.find(f"{{{NS_S}}}tableColumns")
        if table_cols is not None:
            for tc in table_cols.findall(f"{{{NS_S}}}tableColumn"):
                col_name = tc.get("name", "")
                if col_name:
                    columns.append(col_name)
        tables.append({
            "id": table_id,
            "name": name,
            "ref": ref,
            "columns": columns,
            "totalsRow": totals_row,
        })
    return tables


# ── Drawings ──


def parse_drawings(sheet_rels: list, pkg: PackageReader) -> tuple[list[dict], list[dict]]:
    """Parse drawing anchors for images and chart references from pre-read *sheet_rels*."""
    images: list[dict] = []
    charts: list[dict] = []
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
        _parse_drawing_anchor(anchor, drawing_rels, images, charts)
    for anchor in root.iter(f"{{{NS_XDR}}}oneCellAnchor"):
        _parse_drawing_anchor(anchor, drawing_rels, images, charts)

    # Parse chart parts for richer metadata
    for ch in charts:
        if ch.get("part"):
            ch_data = _parse_chart_part(pkg, ch["part"])
            if ch_data.get("type"):
                ch["type"] = ch_data["type"]
            if ch_data.get("title"):
                ch["title"] = ch_data["title"]
            ch["series_count"] = ch_data.get("series_count", 0)
            if ch_data.get("series"):
                ch["series"] = ch_data["series"]

    return images, charts


def _parse_drawing_anchor(anchor: ET.Element, drawing_rels: dict[str, str],
                          images: list[dict], charts: list[dict]) -> None:
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
            img_id = f"image{len(images) + 1}"
            images.append({"id": img_id, "ref": ref, "alt": ""})
            break  # one image per anchor

    # Chart reference (namespace: drawingml/2006/chart, NOT spreadsheetDrawing)
    for ch_elem in anchor.iter(f"{{{NS_C}}}chart"):
        chart_r_id = ch_elem.get(f"{{{NS_R}}}id", "")
        chart_part = drawing_rels.get(chart_r_id, "")
        chart_id = f"chart{len(charts) + 1}"
        charts.append({
            "id": chart_id,
            "ref": ref,
            "type": "",
            "title": "",
            "series_count": 0,
            "part": chart_part,
        })


# ── Chart part parsing ──


_CHART_TYPE_MAP: dict[str, str] = {
    "areaChart": "area",
    "area3DChart": "area3d",
    "barChart": "bar",
    "bar3DChart": "bar3d",
    "bubbleChart": "bubble",
    "doughnutChart": "doughnut",
    "lineChart": "line",
    "line3DChart": "line3d",
    "ofPieChart": "ofPie",
    "pieChart": "pie",
    "pie3DChart": "pie3d",
    "radarChart": "radar",
    "scatterChart": "scatter",
    "surfaceChart": "surface",
    "surface3DChart": "surface3d",
}


def _parse_chart_part(pkg: PackageReader, chart_part: str) -> dict:
    """Parse a chart XML part via shared ChartML parser; return structured dict."""
    try:
        with pkg.open_entry(chart_part) as stream:
            root = ET.parse(stream).getroot()
        info = parse_chart_xml(root)
    except Exception:
        return {"type": "", "title": "", "series_count": 0}

    series_list: list[dict] = []
    for s in info.get("series", []):
        s_item: dict = {
            "index": s["index"],
            "pointCount": max(len(s.get("categories", [])), len(s.get("values", []))),
        }
        if s.get("name"):
            s_item["name"] = s["name"]
        if "min" in s:
            s_item["min"] = s["min"]
        if "max" in s:
            s_item["max"] = s["max"]
        # Full data points
        cats = s.get("categories", [])
        vals = s.get("values", [])
        points: list[dict[str, str]] = []
        for i in range(max(len(cats), len(vals))):
            pt: dict[str, str] = {}
            if i < len(cats):
                pt["category"] = cats[i]
            if i < len(vals):
                pt["value"] = vals[i]
            if pt:
                points.append(pt)
        if points:
            s_item["points"] = points
        series_list.append(s_item)

    return {
        "type": info.get("chart_type", ""),
        "title": info.get("title", ""),
        "series_count": info.get("series_count", 0),
        "series": series_list,
    }


# ── Pivot tables ──


def detect_pivot_tables(sheet_rels: list) -> list[dict]:
    """Detect pivot table relationships from pre-read *sheet_rels*."""
    pivots: list[dict] = []
    for rel in sheet_rels:
        if rel.type == f"{NS_R}/pivotTable":
            pivots.append({"id": f"pivot{len(pivots) + 1}", "ref": "", "name": ""})
    return pivots
