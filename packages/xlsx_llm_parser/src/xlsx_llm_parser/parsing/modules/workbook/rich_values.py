"""Rich values."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning, RelationshipRecord
from ooxml_llm_core.package import PackageReader, rels_path_for_part

from ....models import (
    RichCellValue,
)
from .catalog_parts import (
    _RICH_DATA_PARTS,
    _RICH_STRUCTURE_PARTS,
    NS_R,
    _CatalogParts,
    _find_part,
    _int,
    _local_name,
    _part_names,
)


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
