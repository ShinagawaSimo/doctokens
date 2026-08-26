"""OPC relationship read-only index."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ooxml_llm_core.models import RelationshipRecord

OFFICE_DOCUMENT_RELATIONSHIP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
"""Namespace shared by WordprocessingML, SpreadsheetML, and PresentationML relationships."""


def office_relationship_type(local_name: str) -> str:
    """Return a standard Office-document relationship type from its local name."""
    return f"{OFFICE_DOCUMENT_RELATIONSHIP_NS}/{local_name}"


HYPERLINK_RELATIONSHIP_TYPE = office_relationship_type("hyperlink")


@dataclass(frozen=True)
class RelationshipIndex:
    """Multi-index over OPC relationships, built once and reused for lookups."""

    records: tuple[RelationshipRecord, ...]
    _by_source_id: Mapping[tuple[str, str], RelationshipRecord]
    _by_source: Mapping[str, tuple[RelationshipRecord, ...]]
    _by_type: Mapping[str, tuple[RelationshipRecord, ...]]
    _by_source_type: Mapping[tuple[str, str], tuple[RelationshipRecord, ...]]

    @classmethod
    def from_records(cls, records: Iterable[RelationshipRecord]) -> RelationshipIndex:
        rows = tuple(records)
        by_source_id: dict[tuple[str, str], RelationshipRecord] = {}
        by_source: dict[str, list[RelationshipRecord]] = defaultdict(list)
        by_type: dict[str, list[RelationshipRecord]] = defaultdict(list)
        by_source_type: dict[tuple[str, str], list[RelationshipRecord]] = defaultdict(list)

        for rel in rows:
            by_source_id[(rel.source_part, rel.id)] = rel
            by_source[rel.source_part].append(rel)
            by_type[rel.type].append(rel)
            by_source_type[(rel.source_part, rel.type)].append(rel)

        return cls(
            records=rows,
            _by_source_id=MappingProxyType(by_source_id),
            _by_source=MappingProxyType({key: tuple(value) for key, value in by_source.items()}),
            _by_type=MappingProxyType({key: tuple(value) for key, value in by_type.items()}),
            _by_source_type=MappingProxyType({key: tuple(value) for key, value in by_source_type.items()}),
        )

    def get(self, source_part: str, rel_id: str) -> RelationshipRecord | None:
        return self._by_source_id.get((source_part, rel_id))

    def require(self, source_part: str, rel_id: str) -> RelationshipRecord:
        return self._by_source_id[(source_part, rel_id)]

    def by_source(self, source_part: str) -> tuple[RelationshipRecord, ...]:
        return self._by_source.get(source_part, ())

    def by_type(self, rel_type: str, source_part: str | None = None) -> tuple[RelationshipRecord, ...]:
        if source_part is not None:
            return self._by_source_type.get((source_part, rel_type), ())
        return self._by_type.get(rel_type, ())
