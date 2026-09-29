"""Pivots."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import cast

from ooxml_llm_core.models import ParseWarning, RelationshipRecord
from ooxml_llm_core.package import PackageReader

from ....models import (
    PivotCacheInfo,
    PivotTableInfo,
    SlicerInfo,
    TimelineInfo,
)
from .catalog_parts import NS_R, _bool, _CatalogParts, _int, _local_name, _part_names


@dataclass
class PivotCatalog:
    """Workbook-level PivotTable, cache, slicer, and timeline summaries."""

    caches: list[PivotCacheInfo] = field(default_factory=list)
    _tables_by_part: dict[str, PivotTableInfo] = field(default_factory=dict)
    slicers: list[SlicerInfo] = field(default_factory=list)
    timelines: list[TimelineInfo] = field(default_factory=list)
    _parts: _CatalogParts | None = field(default=None, repr=False)

    @classmethod
    def from_package(cls, pkg: PackageReader, *, warnings: list[ParseWarning]) -> PivotCatalog:
        parts = _CatalogParts(pkg, warnings)
        catalog = cls(_parts=parts)
        workbook = pkg.read_xml("xl/workbook.xml")
        workbook_rels = {record.id: record for record in pkg.read_relationships_for_part("xl/workbook.xml")}
        cache_entries: list[tuple[int, str]] = []
        pivot_caches = next((node for node in workbook.iter() if _local_name(node.tag) == "pivotCaches"), None)
        if pivot_caches is not None:
            for entry in pivot_caches:
                if _local_name(entry.tag) != "pivotCache":
                    continue
                rel_id = entry.get(f"{{{NS_R}}}id", "")
                record = workbook_rels.get(rel_id)
                if record is not None and record.resolved_target:
                    cache_entries.append((_int(entry.get("cacheId")), record.resolved_target))
                else:
                    parts.reference_missing("xl/workbook.xml", f"pivotCache r:id={rel_id}")
        cache_by_id: dict[int, PivotCacheInfo] = {}
        for index, (cache_id, part) in enumerate(cache_entries, 1):
            info = catalog._parse_cache(parts, cache_id, part, index)
            catalog.caches.append(info)
            cache_by_id[cache_id] = info

        for part in _part_names(pkg):
            if "pivottables/" in part.lower() and part.lower().endswith(".xml"):
                table = catalog._parse_table(parts, part, cache_by_id)
                if table is not None:
                    catalog._tables_by_part[part] = table
        catalog.slicers = catalog._parse_slicers(parts)
        catalog.timelines = catalog._parse_timelines(parts)
        return catalog

    def tables_for_relationships(
        self,
        relationships: Iterable[RelationshipRecord],
        start_index: int = 1,
    ) -> list[PivotTableInfo]:
        result: list[PivotTableInfo] = []
        for record in relationships:
            if not record.type.endswith("/pivotTable"):
                continue
            if self._parts is not None and record.resolved_target and not self._parts.pkg.exists(record.resolved_target):
                self._parts.missing(record.resolved_target, record.source_part, record.id)
            elif self._parts is not None and record.resolved_target is None:
                self._parts.reference_missing(record.source_part, f"pivotTable r:id={record.id}")
            table = cast(PivotTableInfo, dict(self._tables_by_part.get(record.resolved_target or "", {})))
            table.setdefault("id", f"pivot{start_index + len(result)}")
            result.append(table)
        return result

    @staticmethod
    def _parse_cache(parts: _CatalogParts, cache_id: int, part: str, index: int) -> PivotCacheInfo:
        root = parts.xml(part, source="xl/workbook.xml")
        info: PivotCacheInfo = {"id": f"cache{index}", "cacheId": cache_id, "fields": []}
        if root is None:
            return info
        info["refreshOnLoad"] = _bool(root.get("refreshOnLoad"))
        info["recordCount"] = _int(root.get("recordCount"))
        source = next((node for node in root.iter() if _local_name(node.tag) == "worksheetSource"), None)
        if source is not None:
            if source.get("ref"):
                info["sourceRef"] = source.get("ref", "")
            if source.get("sheet"):
                info["sourceSheet"] = source.get("sheet", "")
        cache_fields = next((node for node in root.iter() if _local_name(node.tag) == "cacheFields"), None)
        if cache_fields is not None:
            info["fields"] = [
                field_node.get("name", "") for field_node in cache_fields if _local_name(field_node.tag) == "cacheField"
            ]
        extension = next(
            (node for node in root.iter() if _local_name(node.tag) == "pivotCacheDefinition" and node is not root),
            None,
        )
        if extension is not None:
            info["slicerData"] = _bool(extension.get("slicerData"))
            info["timelineData"] = _bool(extension.get("timelineData"))
        return info

    @staticmethod
    def _parse_table(parts: _CatalogParts, part: str, cache_by_id: dict[int, PivotCacheInfo]) -> PivotTableInfo | None:
        root = parts.xml(part)
        if root is None:
            return None
        cache_id = _int(root.get("cacheId"))
        info: PivotTableInfo = {"name": root.get("name", ""), "cacheId": cache_id}
        location = next((node for node in root.iter() if _local_name(node.tag) == "location"), None)
        if location is not None and location.get("ref"):
            info["ref"] = location.get("ref", "")
        cache = cache_by_id.get(cache_id)
        if cache is not None:
            info["fieldNames"] = cache.get("fields", [])
            if "sourceRef" in cache:
                info["sourceRef"] = cache["sourceRef"]
            if "sourceSheet" in cache:
                info["sourceSheet"] = cache["sourceSheet"]
        for child_name, field_kind in (
            ("rowFields", "row"),
            ("colFields", "column"),
            ("pageFields", "page"),
        ):
            parent = next((node for node in root.iter() if _local_name(node.tag) == child_name), None)
            if parent is None:
                continue
            fields: list[str] = []
            for field_node in parent:
                if _local_name(field_node.tag) != "field":
                    continue
                index = _int(field_node.get("x"), -1)
                names = info.get("fieldNames", [])
                fields.append(names[index] if 0 <= index < len(names) else str(index))
            if fields:
                if field_kind == "row":
                    info["rowFields"] = fields
                elif field_kind == "column":
                    info["columnFields"] = fields
                else:
                    info["pageFields"] = fields
        data_fields = next((node for node in root.iter() if _local_name(node.tag) == "dataFields"), None)
        if data_fields is not None:
            info["dataFields"] = [
                field_node.get("name", field_node.get("fld", ""))
                for field_node in data_fields
                if _local_name(field_node.tag) == "dataField"
            ]
        filters = next((node for node in root.iter() if _local_name(node.tag) == "filters"), None)
        if filters is not None:
            info["filters"] = [
                field_node.get("name", field_node.get("fld", ""))
                for field_node in filters.iter()
                if _local_name(field_node.tag) == "filter"
            ]
        style = next((node for node in root.iter() if _local_name(node.tag) == "pivotTableStyleInfo"), None)
        if style is not None and style.get("name"):
            info["style"] = style.get("name", "")
        return info

    @staticmethod
    def _parse_slicers(parts: _CatalogParts) -> list[SlicerInfo]:
        result: list[SlicerInfo] = []
        for part in _part_names(parts.pkg):
            if "slicercache" not in part.lower() or not part.lower().endswith(".xml"):
                continue
            root = parts.xml(part)
            if root is None:
                continue
            definition = next(
                (node for node in root.iter() if _local_name(node.tag) == "slicerCacheDefinition"),
                root,
            )
            info: SlicerInfo = {
                "id": f"slicer{len(result) + 1}",
                "name": definition.get("name", ""),
                "sourceName": definition.get("sourceName", ""),
                "type": "slicer",
            }
            cache = next(
                (node for node in definition.iter() if _local_name(node.tag) in {"tabularSlicerCache", "olapSlicerCache"}),
                None,
            )
            if cache is not None and cache.get("pivotCacheId"):
                info["cacheId"] = _int(cache.get("pivotCacheId"))
            result.append(info)
        return result

    @staticmethod
    def _parse_timelines(parts: _CatalogParts) -> list[TimelineInfo]:
        result: list[TimelineInfo] = []
        for part in _part_names(parts.pkg):
            if "timeline" not in part.lower() or not part.lower().endswith(".xml"):
                continue
            root = parts.xml(part)
            if root is None:
                continue
            definition = next(
                (node for node in root.iter() if _local_name(node.tag) in {"timelineCacheDefinition", "timeline"}),
                root,
            )
            state = next(
                (node for node in root.iter() if _local_name(node.tag) in {"timelineState", "timelineView"}),
                None,
            )
            info: TimelineInfo = {
                "id": f"timeline{len(result) + 1}",
                "name": definition.get("name", ""),
                "sourceName": definition.get("sourceName", ""),
            }
            if definition.get("pivotCacheId"):
                info["cacheId"] = _int(definition.get("pivotCacheId"))
            if state is not None and state.get("level"):
                info["level"] = state.get("level", "")
            result.append(info)
        return result
