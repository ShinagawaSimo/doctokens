"""Catalog parts."""

from __future__ import annotations

import posixpath
from contextlib import suppress
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning, RelationshipRecord
from ooxml_llm_core.package import PackageReader, rels_path_for_part

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
