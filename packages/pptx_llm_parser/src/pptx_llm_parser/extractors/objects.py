"""Embedded object extraction — charts (shared ChartML parser) and SmartArt data models."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.chart_ml import CHART_RELATIONSHIP_TYPES, parse_chart_xml
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

DIAGRAM_DATA_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData"
DIAGRAM_LAYOUT_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramLayout"


@dataclass(frozen=True)
class _ObjectSpec:
    source_part: str
    relationship_id: str
    object_id: str
    part: str


class _LazyChartLookup(Mapping[tuple[str, str], ChartRecord]):
    def __init__(self, owner: EmbeddedObjectExtractor, specs: dict[tuple[str, str], _ObjectSpec]) -> None:
        self._owner = owner
        self._specs = specs
        self._loaded: dict[tuple[str, str], ChartRecord] = {}

    def __getitem__(self, key: tuple[str, str]) -> ChartRecord:
        if key not in self._specs:
            raise KeyError(key)
        if key not in self._loaded:
            record = self._owner._load_chart(self._specs[key])
            if record is None:
                raise KeyError(key)
            self._loaded[key] = record
        return self._loaded[key]

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._specs)

    def __len__(self) -> int:
        return len(self._specs)

    def loaded_values(self) -> list[ChartRecord]:
        return list(self._loaded.values())


class _LazySmartArtLookup(Mapping[tuple[str, str], SmartArtRecord]):
    def __init__(self, owner: EmbeddedObjectExtractor, specs: dict[tuple[str, str], _ObjectSpec]) -> None:
        self._owner = owner
        self._specs = specs
        self._loaded: dict[tuple[str, str], SmartArtRecord] = {}

    def __getitem__(self, key: tuple[str, str]) -> SmartArtRecord:
        if key not in self._specs:
            raise KeyError(key)
        if key not in self._loaded:
            record = self._owner._load_smartart(self._specs[key])
            if record is None:
                raise KeyError(key)
            self._loaded[key] = record
        return self._loaded[key]

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._specs)

    def __len__(self) -> int:
        return len(self._specs)

    def loaded_values(self) -> list[SmartArtRecord]:
        return list(self._loaded.values())


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
        self._chart_lookup: _LazyChartLookup | None = None
        self._smartart_lookup: _LazySmartArtLookup | None = None
        self._chart_specs: dict[tuple[str, str], _ObjectSpec] | None = None
        self._chart_specs_by_id: dict[str, _ObjectSpec] | None = None
        self._smartart_specs: dict[tuple[str, str], _ObjectSpec] | None = None
        self._smartart_specs_by_id: dict[str, _ObjectSpec] | None = None
        self._layout_lookup_cache: LayoutLookup | None = None
        self._layout_categories_by_source: dict[str, str] = {}

    def lazy_charts(self) -> ChartLookup:
        if self._chart_lookup is not None:
            return self._chart_lookup
        specs: dict[tuple[str, str], _ObjectSpec] = {}
        by_id: dict[str, _ObjectSpec] = {}
        chart_records = (record for record in self._relationships.records if record.type in CHART_RELATIONSHIP_TYPES)
        for index, record in enumerate(chart_records, start=1):
            if record.resolved_target is not None:
                spec = _ObjectSpec(record.source_part, record.id, f"chart{index}", record.resolved_target)
                specs[(record.source_part, record.id)] = spec
                by_id[spec.object_id] = spec
        self._chart_specs = specs
        self._chart_specs_by_id = by_id
        self._chart_lookup = _LazyChartLookup(self, specs)
        return self._chart_lookup

    def lazy_smartarts(self) -> tuple[SmartArtLookup, LayoutLookup]:
        if self._smartart_lookup is not None:
            return self._smartart_lookup, self._layout_lookup()
        specs: dict[tuple[str, str], _ObjectSpec] = {}
        by_id: dict[str, _ObjectSpec] = {}
        for index, record in enumerate(self._relationships.by_type(DIAGRAM_DATA_REL_TYPE), start=1):
            if record.resolved_target is not None:
                spec = _ObjectSpec(record.source_part, record.id, f"smartart{index}", record.resolved_target)
                specs[(record.source_part, record.id)] = spec
                by_id[spec.object_id] = spec
        self._smartart_specs = specs
        self._smartart_specs_by_id = by_id
        data_lookup = _LazySmartArtLookup(self, specs)
        self._smartart_lookup = data_lookup
        layout_lookup = self._layout_lookup()
        return data_lookup, layout_lookup

    @property
    def loaded_charts(self) -> list[ChartRecord]:
        return self._chart_lookup.loaded_values() if self._chart_lookup is not None else []

    @property
    def loaded_smartarts(self) -> list[SmartArtRecord]:
        return self._smartart_lookup.loaded_values() if self._smartart_lookup is not None else []

    def chart_by_id(self, resource_id: str) -> ChartRecord | None:
        lookup = self.lazy_charts()
        spec = (self._chart_specs_by_id or {}).get(resource_id)
        if spec is None:
            return None
        return lookup.get((spec.source_part, spec.relationship_id))

    def smartart_by_id(self, resource_id: str) -> SmartArtRecord | None:
        lookup = self.lazy_smartarts()[0]
        spec = (self._smartart_specs_by_id or {}).get(resource_id)
        if spec is None:
            return None
        return lookup.get((spec.source_part, spec.relationship_id))

    def _load_chart(self, spec: _ObjectSpec) -> ChartRecord | None:
        if not self._pkg.exists(spec.part):
            self._warnings.append(
                ParseWarning(code="CHART_PART_MISSING", message=f"Chart part missing: {spec.part}", locator=spec.source_part)
            )
            return None
        try:
            info = parse_chart_xml(self._read_xml(spec.part))
            return cast(ChartRecord, {**info, "id": spec.object_id, "part": spec.part})
        except (ET.ParseError, ValueError, TypeError) as exc:
            self._warnings.append(
                ParseWarning(code="CHART_PARSE_ERROR", message=f"Unable to parse chart: {exc}", locator=spec.part)
            )
            return None

    def _load_smartart(self, spec: _ObjectSpec) -> SmartArtRecord | None:
        if not self._pkg.exists(spec.part):
            self._warnings.append(
                ParseWarning(
                    code="SMARTART_PART_MISSING",
                    message=f"Diagram data part missing: {spec.part}",
                    locator=spec.source_part,
                )
            )
            return None
        try:
            nodes, links = self._parse_diagram_data(self._read_xml(spec.part), spec.part)
            result: SmartArtRecord = {
                "id": spec.object_id,
                "part": spec.part,
                "nodes": nodes,
                "links": links,
                "nodeCount": len(nodes),
                "linkCount": len(links),
            }
            category = self._layout_categories_by_source.get(spec.source_part)
            if category:
                result["layoutType"] = category
            return result
        except (ET.ParseError, ValueError, TypeError) as exc:
            self._warnings.append(
                ParseWarning(code="SMARTART_PARSE_ERROR", message=f"Unable to parse diagram: {exc}", locator=spec.part)
            )
            return None

    def _layout_lookup(self) -> LayoutLookup:
        if self._layout_lookup_cache is not None:
            return self._layout_lookup_cache
        result: LayoutLookup = {}
        for record in self._relationships.by_type(DIAGRAM_LAYOUT_REL_TYPE):
            if record.resolved_target is None or not self._pkg.exists(record.resolved_target):
                continue
            try:
                category = self._parse_layout_category(self._read_xml(record.resolved_target))
            except ET.ParseError:
                category = None
            if category:
                result[(record.source_part, record.id)] = category
                self._layout_categories_by_source.setdefault(record.source_part, category)
        self._layout_lookup_cache = result
        return result

    def extract_charts(self) -> tuple[list[ChartRecord], ChartLookup]:
        charts: list[ChartRecord] = []
        lookup: dict[tuple[str, str], ChartRecord] = {}
        index = 0
        for record in self._relationships.records:
            if record.type not in CHART_RELATIONSHIP_TYPES:
                continue
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
        data_lookup: dict[tuple[str, str], SmartArtRecord] = {}
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
