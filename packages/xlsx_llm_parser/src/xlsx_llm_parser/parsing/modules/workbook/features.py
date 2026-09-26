"""Package-level catalogs for modern Excel features.

The worksheet scanner consumes these catalogs while it is already walking the
cell XML.  Keeping the indirection resolution here prevents every cell or
renderer from reopening metadata, richData, styles, or pivot parts.
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning, RelationshipRecord
from ooxml_llm_core.package import PackageReader, rels_path_for_part

from ....models import (
    CellControl,
    PivotCacheInfo,
    PivotTableInfo,
    RichCellValue,
    SlicerInfo,
    TimelineInfo,
)

NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_RICH_DATA_PARTS = {"richvalue.xml", "rdrichvalue.xml", "rdrichvalues.xml"}
_RICH_STRUCTURE_PARTS = {"richvaluestructure.xml", "rdrichvaluestructure.xml"}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _part_names(pkg: PackageReader) -> list[str]:
    return [entry["name"] for entry in pkg.read_entry_index()]


def _find_part(pkg: PackageReader, names: set[str]) -> str | None:
    for part in _part_names(pkg):
        if posixpath.basename(part).lower() in names:
            return part
    return None


@dataclass(slots=True)
class _CatalogParts:
    pkg: PackageReader
    warnings: list[ParseWarning]
    failed_parts: set[str] = field(default_factory=set)
    _reported: set[tuple[str, str, str]] = field(default_factory=set)

    def warn(self, code: str, locator: str, reason: str, message: str) -> None:
        key = code, locator, reason
        if key not in self._reported:
            self._reported.add(key)
            self.warnings.append(ParseWarning(code, message, locator))

    def xml(self, part: str, *, source: str | None = None, rel_id: str = "") -> ET.Element | None:
        if not self.pkg.exists(part):
            if source is not None:
                self.missing(part, source, rel_id)
            return None
        try:
            return self.pkg.read_xml(part)
        except ET.ParseError as exc:
            self.failed_parts.add(part)
            self.warn("XLSX_CATALOG_XML_INVALID", part, "xml", f"Invalid optional catalog XML: {exc}")
            return None

    def missing(self, part: str, source: str, rel_id: str = "") -> None:
        origin = f"source {source}, relationship {rel_id}" if rel_id else f"source {source}"
        self.warn(
            "XLSX_CATALOG_PART_MISSING",
            part,
            "missing",
            f"Optional catalog target {part} is missing ({origin})",
        )

    def relationships(self, source: str, *, needed: bool = False) -> dict[str, RelationshipRecord]:
        rels_part = rels_path_for_part(source)
        if not self.pkg.exists(rels_part):
            if needed:
                self.missing(rels_part, source)
            return {}
        try:
            return {record.id: record for record in self.pkg.read_relationships_for_part(source)}
        except (ET.ParseError, KeyError, ValueError) as exc:
            self.failed_parts.add(rels_part)
            self.warn("XLSX_CATALOG_RELS_INVALID", rels_part, "relationships", f"Invalid optional catalog relationships: {exc}")
            return {}

    def reference_missing(self, source: str, reference: str) -> None:
        self.warn(
            "XLSX_CATALOG_REFERENCE_UNRESOLVED",
            source,
            reference,
            f"Optional catalog reference {reference!r} could not be resolved",
        )


def _int(value: str | None, default: int = 0) -> int:
    with suppress(TypeError, ValueError):
        return int(value) if value is not None else default
    return default


def _bool(value: str | None) -> bool:
    return value in {"1", "true", "True"}


@dataclass
class RichValueCatalog:
    """Resolve worksheet ``vm`` indices into compact rich-value descriptors."""

    _bindings: list[int | None] = field(default_factory=list)
    _values: list[RichCellValue] = field(default_factory=list)
    _parts: _CatalogParts | None = field(default=None, repr=False)
    _metadata_part: str | None = None
    _rich_part: str | None = None

    @classmethod
    def from_package(cls, pkg: PackageReader, *, warnings: list[ParseWarning]) -> RichValueCatalog:
        parts = _CatalogParts(pkg, warnings)
        metadata_part = "xl/metadata.xml" if pkg.exists("xl/metadata.xml") else None
        if metadata_part is None:
            return cls(_parts=parts)
        metadata = parts.xml(metadata_part)
        if metadata is None:
            return cls()

        future = next(
            (
                element
                for element in metadata
                if _local_name(element.tag) == "futureMetadata" and element.get("name") == "XLRICHVALUE"
            ),
            None,
        )
        future_books = list(future) if future is not None else []
        value_metadata = next(
            (element for element in metadata if _local_name(element.tag) == "valueMetadata"),
            None,
        )
        bindings: list[int | None] = []
        if value_metadata is not None:
            for book in value_metadata:
                rc = next((node for node in book.iter() if _local_name(node.tag) == "rc"), None)
                if rc is None:
                    bindings.append(None)
                    continue
                future_index = _int(rc.get("v"), -1)
                rich_index: int | None = None
                if 0 <= future_index < len(future_books):
                    rvb = next(
                        (node for node in future_books[future_index].iter() if _local_name(node.tag) == "rvb"),
                        None,
                    )
                    if rvb is not None and rvb.get("i") is not None:
                        rich_index = _int(rvb.get("i"), -1)
                if rich_index is None and future_index >= 0:
                    rich_index = future_index
                bindings.append(rich_index if rich_index is not None and rich_index >= 0 else None)

        rich_part = _find_part(pkg, _RICH_DATA_PARTS)
        if rich_part is None:
            return cls(bindings, [], parts, metadata_part, None)
        rich_root = parts.xml(rich_part)
        if rich_root is None:
            return cls(bindings, [], parts, metadata_part, rich_part)

        structures = cls._parse_structures(pkg, parts)
        rel_targets = cls._parse_rich_relationships(pkg, parts)
        web_images = cls._parse_web_images(pkg, parts)
        values = [
            cls._parse_value(node, structures, rel_targets, web_images)
            for node in rich_root.iter()
            if _local_name(node.tag) == "rv"
        ]
        return cls(bindings, values, parts, metadata_part, rich_part)

    def resolve(self, vm: str | None) -> RichCellValue | None:
        """Resolve both Excel's usual 1-based and observed 0-based ``vm`` forms."""
        if vm is None:
            return None
        if self._parts is not None and self._metadata_part is None:
            self._parts.missing("xl/metadata.xml", "cell/@vm")
            return None
        index = _int(vm, -1)
        candidates = [index - 1, index] if index > 0 else [index]
        for binding_index in candidates:
            if 0 <= binding_index < len(self._bindings):
                rich_index = self._bindings[binding_index]
                if rich_index is not None and 0 <= rich_index < len(self._values):
                    return self._values[rich_index]
        has_known_binding = any(
            0 <= binding_index < len(self._bindings) and self._bindings[binding_index] is not None for binding_index in candidates
        )
        if (
            has_known_binding
            and self._parts is not None
            and self._metadata_part is not None
            and self._rich_part is not None
            and self._rich_part not in self._parts.failed_parts
        ):
            self._parts.reference_missing(self._metadata_part, f"vm={vm}")
        return None

    @staticmethod
    def _parse_structures(pkg: PackageReader, parts: _CatalogParts) -> list[tuple[str, list[str]]]:
        part = _find_part(pkg, _RICH_STRUCTURE_PARTS)
        root = parts.xml(part) if part else None
        if root is None:
            return []
        result: list[tuple[str, list[str]]] = []
        for structure in root.iter():
            if _local_name(structure.tag) not in {"s", "structure"}:
                continue
            keys = [key.get("n", key.get("name", "")) for key in structure if _local_name(key.tag) in {"k", "key"}]
            result.append((structure.get("t", ""), keys))
        return result

    @staticmethod
    def _parse_rich_relationships(pkg: PackageReader, parts: _CatalogParts) -> list[RelationshipRecord | None]:
        part = next(
            (name for name in _part_names(pkg) if posixpath.basename(name).lower() in {"richvaluerel.xml", "richvaluerels.xml"}),
            None,
        )
        if part is None:
            return []
        root = parts.xml(part)
        if root is None:
            return []
        slots = [node.get(f"{{{NS_R}}}id", "") for node in root.iter() if _local_name(node.tag) == "rel"]
        relationships = parts.relationships(part, needed=bool(slots))
        rels_part = rels_path_for_part(part)
        targets: list[RelationshipRecord | None] = []
        for slot in slots:
            record = relationships.get(slot)
            if record is None and pkg.exists(rels_part) and rels_part not in parts.failed_parts:
                parts.reference_missing(part, f"r:id={slot}")
            if (
                record is not None
                and record.target_mode != "External"
                and record.resolved_target
                and not pkg.exists(record.resolved_target)
            ):
                parts.missing(record.resolved_target, part, slot)
                record = None
            targets.append(record)
        return targets

    @staticmethod
    def _parse_web_images(pkg: PackageReader, parts: _CatalogParts) -> dict[int, tuple[str, str]]:
        result: dict[int, tuple[str, str]] = {}
        for part in _part_names(pkg):
            if "webimages" not in posixpath.basename(part).lower() or not part.lower().endswith(".xml"):
                continue
            root = parts.xml(part)
            if root is None:
                continue
            addresses = [
                child.get(f"{{{NS_R}}}id", "") for image in root.iter() for child in image if _local_name(child.tag) == "address"
            ]
            rels = parts.relationships(part, needed=bool(addresses))
            rels_part = rels_path_for_part(part)
            candidates = (node for node in root.iter() if _local_name(node.tag) in {"webImage", "image"})
            for index, image in enumerate(candidates):
                address = next((child for child in image if _local_name(child.tag) == "address"), None)
                if address is None:
                    continue
                rel_id = address.get(f"{{{NS_R}}}id", "")
                record = rels.get(rel_id)
                if record is None and pkg.exists(rels_part) and rels_part not in parts.failed_parts:
                    parts.reference_missing(part, f"r:id={rel_id}")
                if record is not None:
                    if record.target_mode != "External" and record.resolved_target and not pkg.exists(record.resolved_target):
                        parts.missing(record.resolved_target, part, rel_id)
                        continue
                    result[index] = (record.resolved_target or "", record.target_mode or "")
        return result

    @classmethod
    def _parse_value(
        cls,
        element: ET.Element,
        structures: list[tuple[str, list[str]]],
        rel_targets: list[RelationshipRecord | None],
        web_images: dict[int, tuple[str, str]],
    ) -> RichCellValue:
        structure_index = _int(element.get("s"), -1)
        structure = structures[structure_index] if 0 <= structure_index < len(structures) else ("", [])
        type_name = element.get("t", "") or structure[0]
        keys = structure[1]
        fields: dict[str, str] = {}
        raw_values: list[tuple[str, str]] = []
        for value in element:
            if _local_name(value.tag) not in {"v", "value"}:
                continue
            kind = value.get("kind", value.get("t", ""))
            raw = value.text or ""
            raw_values.append((kind, raw))
        for index, (_kind, raw) in enumerate(raw_values):
            key = keys[index] if index < len(keys) else f"value{index}"
            fields[key] = raw

        descriptor: RichCellValue = {
            "type": type_name or "rich",
            "fields": fields,
        }
        fallback = next((node for node in element if _local_name(node.tag) == "fb"), None)
        if fallback is not None:
            text = "".join(fallback.itertext()).strip()
            if text:
                descriptor["fallback"] = text
        display = fields.get("_DisplayString") or fields.get("Text") or fields.get("Display") or descriptor.get("fallback", "")
        if display:
            descriptor["display"] = display

        image_key = next(
            (key for key in fields if "ImageIdentifier" in key or key.startswith("_rvRel:")),
            None,
        )
        slot = _int(fields.get(image_key, "-1"), -1) if image_key else -1
        if slot < 0:
            for kind, raw in raw_values:
                if kind in {"rel", "r"}:
                    slot = _int(raw, -1)
                    break
        if image_key or type_name.lower() in {"image", "_localimage", "_webimage", "webimage"}:
            if "WebImageIdentifier" in fields:
                web_target = web_images.get(_int(fields["WebImageIdentifier"], -1))
                if web_target is not None:
                    if web_target[1] == "External":
                        descriptor["imageUrl"] = web_target[0]
                    else:
                        descriptor["imagePart"] = web_target[0]
            if 0 <= slot < len(rel_targets):
                record = rel_targets[slot]
                if record is not None:
                    if record.target_mode == "External":
                        descriptor["imageUrl"] = record.resolved_target or record.target
                    elif record.resolved_target:
                        descriptor["imagePart"] = record.resolved_target
            if alt := fields.get("Text") or fields.get("AltText"):
                descriptor["alt"] = alt
            if sizing := fields.get("ImageSizing"):
                descriptor["sizing"] = _int(sizing)
            if width := fields.get("ImageWidth"):
                descriptor["width"] = width
            if height := fields.get("ImageHeight"):
                descriptor["height"] = height
            descriptor["computed"] = fields.get("ComputedImage") == "1"
            descriptor["decorative"] = fields.get("CalcOrigin") == "6"
        return descriptor


@dataclass
class CellControlCatalog:
    """Resolve Excel feature-property bags into style-indexed cell controls."""

    by_style: dict[int, CellControl] = field(default_factory=dict)

    @classmethod
    def from_package(cls, pkg: PackageReader, *, warnings: list[ParseWarning]) -> CellControlCatalog:
        parts = _CatalogParts(pkg, warnings)
        roots: list[ET.Element] = []
        for part in _part_names(pkg):
            lower = part.lower()
            if lower.endswith(".xml") and (lower.endswith("styles.xml") or "featurepropertybag" in lower):
                root = parts.xml(part)
                if root is not None:
                    roots.append(root)
        bags: list[ET.Element] = [
            node
            for root in roots
            for node in root.iter()
            if _local_name(node.tag) in {"bag", "featurePropertyBag"} and node.get("type")
        ]
        values = [cls._bag_values(bag) for bag in bags]
        checkbox_by_index: dict[int, CellControl] = {}
        for index, (bag, props) in enumerate(zip(bags, values, strict=True)):
            if bag.get("type") == "Checkbox":
                checkbox_by_index[index] = {"kind": "checkbox", "default": _int(props.get("default"), 0)}
        controls_by_index: dict[int, CellControl] = {}
        for index, (bag, props) in enumerate(zip(bags, values, strict=True)):
            if bag.get("type") != "XFControls":
                continue
            checkbox_index = _int(props.get("CellControl"), -1)
            if checkbox_index in checkbox_by_index:
                controls_by_index[index] = checkbox_by_index[checkbox_index]

        mapped_complements: list[int] = []
        for bag, props in zip(bags, values, strict=True):
            if bag.get("type") == "XFComplements":
                mapped_complements.extend(_int(item, -1) for item in props.get("MappedFeaturePropertyBags", "").split(","))

        style_to_complement: dict[int, int] = {}
        for root in roots:
            cell_xfs = next((node for node in root.iter() if _local_name(node.tag) == "cellXfs"), None)
            if cell_xfs is None:
                continue
            for style_index, xf in enumerate(cell_xfs):
                marker = next((node for node in xf.iter() if _local_name(node.tag) == "xfComplement"), None)
                if marker is not None:
                    style_to_complement[style_index] = _int(marker.get("i"), -1)
        if style_to_complement and not bags and not any("featurepropertybag" in part.lower() for part in parts.failed_parts):
            for complement_index in sorted(set(style_to_complement.values())):
                parts.reference_missing("xl/styles.xml", f"xfComplement i={complement_index}")
        result: dict[int, CellControl] = {}
        for style_index, complement_index in style_to_complement.items():
            if 0 <= complement_index < len(mapped_complements):
                bag_index = mapped_complements[complement_index]
                if 0 <= bag_index < len(bags) and bags[bag_index].get("type") == "XFComplement":
                    controls_index = _int(values[bag_index].get("XFControls"), -1)
                    if controls_index in controls_by_index:
                        result[style_index] = controls_by_index[controls_index]
        return cls(result)

    @staticmethod
    def _bag_values(bag: ET.Element) -> dict[str, str]:
        values: dict[str, str] = {}
        for child in bag:
            key = child.get("k")
            if not key:
                continue
            text = (child.text or "").strip()
            if _local_name(child.tag) == "a":
                text = ",".join((item.text or "").strip() for item in child)
            values[key] = text
        return values


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
