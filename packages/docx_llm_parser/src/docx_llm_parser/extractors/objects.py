"""Parse charts and SmartArt referenced by DrawingML in DOCX files."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.chart_ml import parse_chart_xml

from ..core.constants import qualified_name
from ..core.models import (
    Chart,
    ChartSeries,
    ObjectLookup,
    ParseWarning,
    SmartArt,
    SmartArtLink,
    SmartArtNode,
)
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex

CHART_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
DIAGRAM_DATA_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData"
DIAGRAM_LAYOUT_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramLayout"


class EmbeddedObjectExtractor:
    """Build a lightweight object index from chart/diagram relationships."""

    def __init__(
        self,
        package: PackageReader,
        relationships: RelationshipIndex,
        warnings: list[ParseWarning],
    ) -> None:
        self.package = package
        self.relationships = relationships
        self.warnings = warnings

    def extract(self) -> tuple[ObjectLookup, list[Chart], list[SmartArt]]:
        """Parse charts and SmartArt, returning a `(sourcePart, rId)` index."""
        lookup: ObjectLookup = {}
        layout_map = self._build_layout_map()
        charts = self._extract_charts(lookup)
        smartarts = self._extract_smartarts(lookup, layout_map)
        return lookup, charts, smartarts

    def _build_layout_map(self) -> dict[str, str]:
        """Build a mapping from SmartArt data parts to layout types.

        Reads layoutN.xml parts via DIAGRAM_LAYOUT_REL_TYPE relationships
        and extracts the trailing category name of catLst/cat@type.
        """
        layout_map: dict[str, str] = {}
        for rel in self.relationships.by_type(DIAGRAM_LAYOUT_REL_TYPE):
            target = rel.resolved_target
            if not target or not self.package.exists(target):
                continue
            try:
                with self.package.open_entry(target) as stream:
                    root = ET.parse(stream).getroot()
                layout_type = _layout_type(root)
                if layout_type:
                    layout_map[rel.source_part] = layout_type
            except Exception as exc:
                self._warn(
                    "LAYOUT_PARSE_FAILED",
                    f"Failed to parse layout part {target}: {exc}",
                    part=target,
                )
        return layout_map

    def _extract_charts(self, lookup: ObjectLookup) -> list[Chart]:
        """Parse the chart parts targeted by chart relationships."""
        charts: list[Chart] = []
        for chart_index, rel in enumerate(self.relationships.by_type(CHART_REL_TYPE), start=1):
            chart_id = f"chart{chart_index}"
            target = rel.resolved_target
            if rel.target_mode == "External" or not target or not self.package.exists(target):
                # Keep a warning when the chart part is missing; the body falls back to a
                # lightweight placeholder.
                self._warn(
                    "CHART_TARGET_MISSING",
                    f"Chart target is missing: {target}",
                    part=rel.source_part,
                )
                continue
            try:
                with self.package.open_entry(target) as stream:
                    root = ET.parse(stream).getroot()
                chart = parse_chart_root(root, chart_id, target)
            except Exception as exc:
                self._warn(
                    "CHART_PARSE_FAILED",
                    f"Failed to parse chart part {target}: {exc}",
                    part=target,
                )
                continue
            chart["sourcePart"] = rel.source_part
            chart["relationshipId"] = rel.id
            charts.append(chart)
            lookup[(rel.source_part, rel.id)] = chart
        return charts

    def _extract_smartarts(
        self,
        lookup: ObjectLookup,
        layout_map: dict[str, str],
    ) -> list[SmartArt]:
        """Parse the diagram data parts targeted by SmartArt data model relationships."""
        smartarts: list[SmartArt] = []
        for item_index, rel in enumerate(self.relationships.by_type(DIAGRAM_DATA_REL_TYPE), start=1):
            smartart_id = f"smartart{item_index}"
            target = rel.resolved_target
            if rel.target_mode == "External" or not target or not self.package.exists(target):
                self._warn(
                    "SMARTART_TARGET_MISSING",
                    f"SmartArt data target is missing: {target}",
                    part=rel.source_part,
                )
                continue
            try:
                with self.package.open_entry(target) as stream:
                    root = ET.parse(stream).getroot()
                smartart = parse_smartart_root(root, smartart_id, target)
            except Exception as exc:
                self._warn(
                    "SMARTART_PARSE_FAILED",
                    f"Failed to parse SmartArt data part {target}: {exc}",
                    part=target,
                )
                continue
            # Inject the layout type (the category name extracted from layoutN.xml)
            layout_type = layout_map.get(rel.source_part)
            if layout_type:
                smartart["layoutType"] = layout_type
            smartart["sourcePart"] = rel.source_part
            smartart["relationshipId"] = rel.id
            smartarts.append(smartart)
            lookup[(rel.source_part, rel.id)] = smartart
        return smartarts

    def _warn(self, code: str, message: str, part: str | None = None) -> None:
        """Record an object-parsing warning."""
        self.warnings.append(ParseWarning(code=code, message=message, locator=part))


def parse_chart_root(root: ET.Element, chart_id: str, part_name: str) -> Chart:
    """Extract chart information from the chart XML, delegating to the shared ChartML parser."""
    info = parse_chart_xml(root)
    series: list[ChartSeries] = []
    for s in info.get("series", []):
        row: ChartSeries = {
            "index": s["index"],
            "pointCount": max(len(s.get("categories", [])), len(s.get("values", []))),
            "preview": s.get("preview", ""),
        }
        if s.get("name"):
            row["name"] = s["name"]
        if "min" in s:
            row["min"] = s["min"]
        if "max" in s:
            row["max"] = s["max"]
        if s.get("formula"):
            row["formula"] = s["formula"]
        if s.get("categories"):
            row["categories"] = s["categories"]
        if s.get("values"):
            row["values"] = s["values"]
        series.append(row)

    chart: Chart = {
        "id": chart_id,
        "type": "chart",
        "chartType": info.get("chart_type", "unknown"),
        "part": part_name,
        "seriesCount": info.get("series_count", 0),
        "pointCount": info.get("point_count", 0),
        "series": series,
    }
    title = info.get("title", "")
    if title:
        chart["title"] = title
    return chart


def parse_smartart_root(root: ET.Element, smartart_id: str, part_name: str) -> SmartArt:
    """Extract node text and connections from the SmartArt data model."""
    nodes: list[SmartArtNode] = []
    node_index_by_model_id: dict[str, int] = {}
    for point in root.iter(qualified_name("dgm", "pt")):
        model_id = point.attrib["modelId"]
        text = _drawing_text(point)
        if not text:
            continue
        node: SmartArtNode = {"modelId": model_id, "text": text}
        point_type = point.get("type")
        if point_type:
            node["kind"] = point_type
        node_index_by_model_id[model_id] = len(nodes) + 1
        nodes.append(node)

    links: list[SmartArtLink] = []
    raw_link_count = 0
    for connection in root.iter(qualified_name("dgm", "cxn")):
        raw_link_count += 1
        source = connection.get("srcId")
        target = connection.get("destId")
        if source is not None and target is not None and source in node_index_by_model_id and target in node_index_by_model_id:
            # The final XML references nodes by short ordinal numbers to avoid exposing
            # lengthy modelIds.
            link: SmartArtLink = {
                "from": node_index_by_model_id[source],
                "to": node_index_by_model_id[target],
            }
            kind = connection.get("type")
            if kind:
                link["kind"] = kind
            links.append(link)

    return {
        "id": smartart_id,
        "type": "smartart",
        "part": part_name,
        "nodeCount": len(nodes),
        "linkCount": len(links),
        "rawLinkCount": raw_link_count,
        "nodes": nodes,
        "links": links,
    }


def _drawing_text(node: ET.Element) -> str:
    """Read the a:t text inside DrawingML/diagram rich text."""
    parts = [item.text or "" for item in node.iter() if item.tag == qualified_name("a", "t")]
    return "".join(parts).strip()


def _layout_type(root: ET.Element) -> str | None:
    """Extract the layout category name from a dgm:layoutDef.

    Reads the type attribute of the first cat element in catLst and takes
    the last URI segment as the category name (e.g. process, cycle,
    hierarchy, list, relationship, matrix, pyramid).
    """
    cat = root.find(".//" + qualified_name("dgm", "cat"))
    if cat is None:
        return None
    type_uri = cat.get("type", "")
    if not type_uri:
        return None
    # Take the last URI segment as the category name
    return type_uri.rstrip("/").rsplit("/", 1)[-1]
