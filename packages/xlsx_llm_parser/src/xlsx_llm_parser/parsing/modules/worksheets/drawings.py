"""Drawings."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.chart_ml import CHART_RELATIONSHIP_TYPES, parse_chart_xml
from ooxml_llm_core.models import ParseWarning, RelationshipRecord
from ooxml_llm_core.package import PackageReader

from ...._utils import col_letter
from ....models import (
    ChartPoint,
    DrawingChart,
    DrawingChartSeries,
    DrawingImage,
)
from .post_common import NS_R, _local_name, _warn

_REL_DRAWING = f"{NS_R}/drawing"


NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"


NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


# ── Drawings ──


def parse_drawings(
    sheet_rels: list[RelationshipRecord],
    pkg: PackageReader,
    *,
    image_start: int = 1,
    chart_start: int = 1,
    warnings: list[ParseWarning] | None = None,
) -> tuple[list[DrawingImage], list[DrawingChart]]:
    """Parse drawing anchors for images and chart references from pre-read *sheet_rels*."""
    images: list[DrawingImage] = []
    charts: list[DrawingChart] = []
    drawing_rel = next((rel for rel in sheet_rels if rel.type == _REL_DRAWING), None)
    if drawing_rel is None:
        return images, charts
    drawing_part = drawing_rel.resolved_target
    if not drawing_part or not pkg.exists(drawing_part):
        _warn(
            warnings, "DRAWING_PART_MISSING", "Referenced drawing part is missing", f"{drawing_rel.source_part}#{drawing_rel.id}"
        )
        return images, charts

    # Drawing relationships for image/chart media
    drawing_rels: dict[str, RelationshipRecord] = {}
    try:
        for rel in pkg.read_relationships_for_part(drawing_part):
            drawing_rels[rel.id] = rel
    except ET.ParseError as exc:
        _warn(warnings, "DRAWING_RELS_XML_INVALID", f"Invalid drawing relationships XML: {exc}", drawing_part)

    try:
        root = pkg.read_xml(drawing_part)
    except ET.ParseError as exc:
        _warn(warnings, "DRAWING_XML_INVALID", f"Invalid drawing XML: {exc}", drawing_part)
        return images, charts

    for anchor_name in ("twoCellAnchor", "oneCellAnchor", "absoluteAnchor"):
        for anchor in root.iter(f"{{{NS_XDR}}}{anchor_name}"):
            _parse_drawing_anchor(anchor, drawing_rels, images, charts, image_start, chart_start)

    # Parse chart parts for richer metadata
    for chart in charts:
        if chart.get("part"):
            chart_data = _parse_chart_part(pkg, chart["part"], warnings)
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


def _parse_chart_part(pkg: PackageReader, chart_part: str, warnings: list[ParseWarning] | None = None) -> DrawingChart:
    """Parse a chart XML part via shared ChartML parser; return structured dict."""
    if not chart_part or not pkg.exists(chart_part):
        _warn(warnings, "CHART_PART_MISSING", "Referenced chart part is missing", chart_part)
        return {"type": "", "title": "", "series_count": 0}
    try:
        root = pkg.read_xml(chart_part)
        chart_info = parse_chart_xml(root)
    except Exception as exc:
        _warn(warnings, "CHART_XML_INVALID", f"Invalid chart XML: {exc}", chart_part)
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
