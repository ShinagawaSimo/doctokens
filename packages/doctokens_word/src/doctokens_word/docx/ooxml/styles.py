"""Resolve typed style inheritance and the reading-property cascade."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ..model import ParseWarning, RunFormat, StyleRecord, append_warning
from .formatting import merge_paragraph_borders, merge_run_formats

_TOGGLES = {"bold", "italic", "smallCaps", "strike"}


def merge_properties(*records: StyleRecord) -> StyleRecord:
    result = StyleRecord(style_id="")
    for record in records:
        result.run_format = merge_run_formats(result.run_format, record.run_format)
        result.borders = merge_paragraph_borders(result.borders, record.borders)
        for name in (
            "alignment",
            "outline_level",
            "numbering_num_id",
            "numbering_level",
            "cell_background",
            "row_band_size",
            "column_band_size",
        ):
            if (value := getattr(record, name)) is not None:
                setattr(result, name, value)
    return result


class StyleMap:
    """Per-document style index; every hierarchy level resolves independently."""

    def __init__(
        self, records: dict[str, StyleRecord], warnings: list[ParseWarning], *, defaults: StyleRecord | None = None
    ) -> None:
        self.records: Mapping[str, StyleRecord] = MappingProxyType(dict(records))
        self.warnings = warnings
        self.defaults = defaults or StyleRecord(style_id="")
        self._cache: dict[str, StyleRecord] = {}
        self._region_cache: dict[tuple[str, str], StyleRecord] = {}
        self.default_ids = {record.type: key for key, record in records.items() if record.is_default}

    def style_id(self, style_id: str | None, kind: str) -> str | None:
        if style_id and (record := self.records.get(style_id)) and record.type == kind:
            return style_id
        return self.default_ids.get(kind)

    def _chain(self, style_id: str | None) -> list[StyleRecord]:
        chain: list[StyleRecord] = []
        visited: set[str] = set()
        while style_id:
            if style_id in visited:
                append_warning(
                    self.warnings, "STYLE_INHERITANCE_CYCLE", f"Style inheritance cycle at {style_id}", part="word/styles.xml"
                )
                break
            visited.add(style_id)
            record = self.records.get(style_id)
            if record is None:
                break
            chain.append(record)
            parent = self.records.get(record.based_on or "")
            style_id = record.based_on if parent and parent.type == record.type else None
        return list(reversed(chain))

    def resolve(self, style_id: str | None) -> StyleRecord:
        if not style_id:
            return StyleRecord(style_id="")
        if style_id not in self._cache:
            self._cache[style_id] = merge_properties(*self._chain(style_id))
        return self._cache[style_id]

    def paragraph(self, style_id: str | None, table: StyleRecord | None = None) -> StyleRecord:
        return merge_properties(
            self.defaults, table or StyleRecord(style_id=""), self.resolve(self.style_id(style_id, "paragraph"))
        )

    def run_format(
        self,
        paragraph_style: str | None,
        character_style: str | None,
        table: StyleRecord | None = None,
        inherited: RunFormat | None = None,
        direct: RunFormat | None = None,
    ) -> RunFormat:
        layers = [
            (table or StyleRecord(style_id="")).run_format,
            self.resolve(self.style_id(paragraph_style, "paragraph")).run_format,
            self.resolve(self.style_id(character_style, "character")).run_format,
        ]
        result = merge_run_formats(self.defaults.run_format, *layers)
        for key in _TOGGLES:
            if key in self.defaults.run_format or any(key in layer for layer in layers):
                result[key] = (
                    self.defaults.run_format.get(key) is True or sum(layer.get(key) is True for layer in layers) % 2 == 1
                )
        return merge_run_formats(result, inherited, direct)

    def table(self, style_id: str | None, regions: list[str]) -> StyleRecord:
        style_id = self.style_id(style_id, "table")
        result = self.resolve(style_id)
        for name in ["wholeTable", *regions]:
            key = (style_id or "", name)
            if key not in self._region_cache:
                self._region_cache[key] = merge_properties(
                    *(record.table_regions[name] for record in self._chain(style_id) if name in record.table_regions)
                )
            result = merge_properties(result, self._region_cache[key])
        return result

    def resolve_heading_level(self, style_id: str | None) -> int | None:
        level = self.paragraph(style_id).outline_level
        return level + 1 if level is not None and level < 9 else None

    def resolve_numbering(self, style_id: str | None) -> tuple[str, int] | None:
        record = self.paragraph(style_id)
        return (record.numbering_num_id, record.numbering_level or 0) if record.numbering_num_id is not None else None

    def numbering_style_num_ids(self) -> Mapping[str, str]:
        return MappingProxyType(
            {
                key: record.numbering_num_id
                for key, record in self.records.items()
                if record.type == "numbering" and record.numbering_num_id is not None
            }
        )
