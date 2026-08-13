"""Embedded object extraction — charts (shared ChartML parser) and SmartArt data models."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.chart_ml import parse_chart_xml
from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.relationships import RelationshipIndex

from ..core.constants import local_name
from ..core.models import (
    ChartLookup,
    ChartRecord,
    LayoutLookup,
    SmartArtLink,
    SmartArtLookup,
    SmartArtNode,
    SmartArtRecord,
)
from ..core.package import PackageReader

CHART_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
DIAGRAM_DATA_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData"
DIAGRAM_LAYOUT_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramLayout"


class EmbeddedObjectExtractor:
    """Parse embedded chart and diagram parts into lightweight records."""

    def __init__(
        self,
        pkg: PackageReader,
        relationships: RelationshipIndex,
        warnings: list[ParseWarning],
    ) -> None:
        self._pkg = pkg
        self._relationships = relationships
        self._warnings = warnings

    def extract_charts(self) -> tuple[list[ChartRecord], ChartLookup]:
        charts: list[ChartRecord] = []
        lookup: ChartLookup = {}
        index = 0
        for record in self._relationships.by_type(CHART_REL_TYPE):
            index += 1
            chart_id = f"chart{index}"
            part = record.resolved_target
            if part is None or not self._pkg.exists(part):
                self._warnings.append(
                    ParseWarning(
                        code="CHART_PART_MISSING",
                        message=f"Chart part missing: {part}",
                        locator=record.source_part,
                    )
                )
                continue
            root = self._read_xml(part)
            info = parse_chart_xml(root)
            # ChartInfo keys are structurally compatible with ChartRecord; the
            # unpack merge cannot be verified statically, so cast is contained here.
            chart = cast(ChartRecord, {**info, "id": chart_id, "part": part})
            charts.append(chart)
            lookup[(record.source_part, record.id)] = chart
        return charts, lookup

    def extract_smartarts(self) -> tuple[list[SmartArtRecord], SmartArtLookup, LayoutLookup]:
        smartarts: list[SmartArtRecord] = []
        data_lookup: SmartArtLookup = {}
        index = 0
        for record in self._relationships.by_type(DIAGRAM_DATA_REL_TYPE):
            index += 1
            smartart_id = f"smartart{index}"
            part = record.resolved_target
            if part is None or not self._pkg.exists(part):
                self._warnings.append(
                    ParseWarning(
                        code="SMARTART_PART_MISSING",
                        message=f"Diagram data part missing: {part}",
                        locator=record.source_part,
                    )
                )
                continue
            root = self._read_xml(part)
            nodes, links = self._parse_diagram_data(root, part)
            smartart: SmartArtRecord = {
                "id": smartart_id,
                "part": part,
                "nodes": nodes,
                "links": links,
                "nodeCount": len(nodes),
                "linkCount": len(links),
            }
            smartarts.append(smartart)
            data_lookup[(record.source_part, record.id)] = smartart
        layout_lookup: LayoutLookup = {}
        for record in self._relationships.by_type(DIAGRAM_LAYOUT_REL_TYPE):
            part = record.resolved_target
            if part is None or not self._pkg.exists(part):
                continue
            category = self._parse_layout_category(self._read_xml(part))
            if category:
                layout_lookup[(record.source_part, record.id)] = category
        return smartarts, data_lookup, layout_lookup

    def _parse_diagram_data(self, root: ET.Element, part: str) -> tuple[list[SmartArtNode], list[SmartArtLink]]:
        nodes: list[SmartArtNode] = []
        node_map: dict[str, int] = {}
        links: list[SmartArtLink] = []
        for element in root.iter():
            name = local_name(element.tag)
            if name == "pt":
                ordinal = len(nodes) + 1
                node_map[element.get("modelId", "")] = ordinal
                nodes.append({"id": ordinal, "text": self._node_text(element)})
            elif name == "cxn":
                from_id = node_map.get(element.get("fromModelId", ""))
                to_id = node_map.get(element.get("toModelId", ""))
                if from_id is None or to_id is None:
                    self._warnings.append(
                        ParseWarning(
                            code="SMARTART_UNRESOLVED_LINK",
                            message="dgm:cxn references unknown modelId",
                            locator=part,
                        )
                    )
                    continue
                links.append({"from": from_id, "to": to_id})
        return nodes, links

    @staticmethod
    def _node_text(pt: ET.Element) -> str:
        parts = [element.text for element in pt.iter() if local_name(element.tag) == "t" and element.text is not None]
        return "".join(parts)

    @staticmethod
    def _parse_layout_category(root: ET.Element) -> str | None:
        for element in root.iter():
            if local_name(element.tag) == "cat":
                type_uri = element.get("type")
                if type_uri:
                    return type_uri.rsplit("/", 1)[-1]
        return None

    def _read_xml(self, part: str) -> ET.Element:
        with self._pkg.open_entry(part) as stream:
            return ET.parse(stream).getroot()
