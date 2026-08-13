"""Parse word/styles.xml and identify heading levels from styles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from types import MappingProxyType
from xml.etree import ElementTree as ET

from ..core.constants import attr, first_child, qualified_name
from ..core.models import ParseWarning, RunFormat, StyleRecord, append_warning
from ..core.package import PackageReader
from .formatting import merge_run_formats, parse_run_format


class StyleMap:
    """Style index; read-only once built, safe for concurrent parsing."""

    def __init__(self, records: dict[str, StyleRecord], warnings: list[ParseWarning]) -> None:
        self.records: Mapping[str, StyleRecord] = MappingProxyType(dict(records))
        self.warnings = warnings
        self._heading_level_cache: dict[str, int | None] = {}
        self._numbering_cache: dict[str, tuple[str, int] | None] = {}
        self._run_format_cache: dict[str, RunFormat] = {}

    def resolve_heading_level(self, style_id: str | None) -> int | None:
        """Resolve the heading level from a styleId; no paragraph-text heuristics."""
        if not style_id:
            return None
        if style_id not in self._heading_level_cache:
            # The style inheritance chain is resolved once; later hot paths (runs/paragraphs) read the cache directly.
            self._heading_level_cache[style_id] = self._resolve_heading_level(style_id, visited=set())
        return self._heading_level_cache[style_id]

    def resolve_numbering(self, style_id: str | None) -> tuple[str, int] | None:
        """Resolve the numbering information a style explicitly binds."""
        if not style_id:
            return None
        if style_id not in self._numbering_cache:
            # Numbering-style inheritance is cached too, avoiding repeated recursion per paragraph.
            self._numbering_cache[style_id] = self._resolve_numbering(style_id, visited=set())
        return self._numbering_cache[style_id]

    def resolve_run_format(self, style_id: str | None) -> RunFormat:
        """Resolve the visible run format of a styleId after inheritance."""
        if not style_id:
            return {}
        if style_id not in self._run_format_cache:
            # Runs usually far outnumber styles, so caching notably reduces repeated computation in large documents.
            self._run_format_cache[style_id] = self._resolve_run_format(style_id, visited=set())
        return self._run_format_cache[style_id]

    def to_debug_list(self) -> list[dict[str, object]]:
        """Produce a style summary for debug output."""
        rows: list[dict[str, object]] = []
        for style_id in sorted(self.records):
            record = self.records[style_id]
            row = asdict(record)
            row["resolved_heading_level"] = self.resolve_heading_level(style_id)
            rows.append(row)
        return rows

    def _resolve_heading_level(self, style_id: str, visited: set[str]) -> int | None:
        """Recursively resolve the outline level along the basedOn inheritance chain."""
        if style_id in visited:
            # Cyclic style inheritance cannot be recursed to the end; record a warning and stop.
            append_warning(
                self.warnings,
                "STYLE_INHERITANCE_CYCLE",
                f"Style inheritance cycle detected at {style_id}",
                part="word/styles.xml",
            )
            return None

        record = self.records.get(style_id)
        if record is None:
            # No heading fallback when the style table has no explicit record.
            return None

        if record.outline_level is not None:
            # OOXML outlineLvl is 0-based; output for the LLM is 1-based.
            return record.outline_level + 1

        if record.based_on:
            # Only follow the inheritance chain for an explicit outlineLvl; never guess from style names.
            visited.add(style_id)
            return self._resolve_heading_level(record.based_on, visited)
        return None

    def _resolve_numbering(self, style_id: str, visited: set[str]) -> tuple[str, int] | None:
        """Recursively resolve the numPr along the basedOn inheritance chain."""
        if style_id in visited:
            self.warnings.append(
                ParseWarning(
                    code="STYLE_NUMBERING_INHERITANCE_CYCLE",
                    message=f"Style numbering inheritance cycle detected at {style_id}",
                    locator="word/styles.xml",
                )
            )
            return None

        record = self.records.get(style_id)
        if record is None:
            return None

        if record.numbering_num_id is not None:
            # numPr in a style is an explicit Word structure, not a guess from the style name.
            return (record.numbering_num_id, record.numbering_level or 0)

        if record.based_on:
            visited.add(style_id)
            return self._resolve_numbering(record.based_on, visited)
        return None

    def _resolve_run_format(self, style_id: str, visited: set[str]) -> RunFormat:
        """Recursively merge run formats along the basedOn inheritance chain."""
        if style_id in visited:
            self.warnings.append(
                ParseWarning(
                    code="STYLE_FORMAT_INHERITANCE_CYCLE",
                    message=f"Style format inheritance cycle detected at {style_id}",
                    locator="word/styles.xml",
                )
            )
            return {}

        record = self.records.get(style_id)
        if record is None:
            return {}

        inherited: RunFormat = {}
        if record.based_on:
            visited.add(style_id)
            inherited = self._resolve_run_format(record.based_on, visited)
        return merge_run_formats(inherited, record.run_format)


class StylesParser:
    """Read styles.xml and build a StyleMap."""

    def __init__(self, package: PackageReader, warnings: list[ParseWarning]) -> None:
        self.package = package
        self.warnings = warnings

    def parse(self) -> StyleMap:
        """Parse the styles file; return an empty style table when it is missing."""
        if not self.package.exists("word/styles.xml"):
            # Paragraphs can still be extracted without the styles file, but headings cannot be reliably identified.
            self.warnings.append(
                ParseWarning(
                    code="MISSING_STYLES",
                    message="word/styles.xml is missing; heading detection will be limited.",
                    locator="word/styles.xml",
                )
            )
            return StyleMap({}, self.warnings)

        with self.package.open_entry("word/styles.xml") as stream:
            root = ET.parse(stream).getroot()

        records: dict[str, StyleRecord] = {}
        for style in root.findall(qualified_name("w", "style")):
            style_id = attr(style, "w", "styleId")
            if not style_id:
                # A style without a styleId cannot be referenced from the body.
                continue
            record = StyleRecord(
                style_id=style_id,
                type=attr(style, "w", "type") or "unknown",
                is_default=(attr(style, "w", "default") or "").lower() in {"1", "true"},
            )
            name = first_child(style, "w", "name")
            based_on = first_child(style, "w", "basedOn")
            next_style = first_child(style, "w", "next")
            paragraph_properties = first_child(style, "w", "pPr")
            run_properties = first_child(style, "w", "rPr")
            outline = first_child(paragraph_properties, "w", "outlineLvl")
            numbering_properties = first_child(paragraph_properties, "w", "numPr")

            record.name = attr(name, "w", "val") if name is not None else None
            record.based_on = attr(based_on, "w", "val") if based_on is not None else None
            record.next = attr(next_style, "w", "val") if next_style is not None else None
            record.run_format = parse_run_format(run_properties)
            outline_val = attr(outline, "w", "val") if outline is not None else None
            if outline_val is not None:
                try:
                    record.outline_level = int(outline_val)
                except ValueError:
                    # An invalid outlineLvl does not affect parsing of other styles.
                    self.warnings.append(
                        ParseWarning(
                            code="INVALID_OUTLINE_LEVEL",
                            message=f"Invalid outline level {outline_val!r} for style {style_id}",
                            locator="word/styles.xml",
                        )
                    )
            numid_elem = first_child(numbering_properties, "w", "numId")
            level_elem = first_child(numbering_properties, "w", "ilvl")
            numbering_id = attr(numid_elem, "w", "val") if numid_elem is not None else None
            level_str = attr(level_elem, "w", "val") if level_elem is not None else None
            if numbering_id is not None:
                record.numbering_num_id = numbering_id
                try:
                    record.numbering_level = int(level_str) if level_str is not None else 0
                except ValueError:
                    # An invalid style numbering level falls back to level 0 while keeping the warning.
                    record.numbering_level = 0
                    self.warnings.append(
                        ParseWarning(
                            code="INVALID_STYLE_NUMBERING_LEVEL",
                            message=(f"Invalid numbering level {level_str!r} for style {style_id}"),
                            locator="word/styles.xml",
                        )
                    )
            records[style_id] = record

        style_map = StyleMap(records, self.warnings)
        for record in records.values():
            record.resolved_heading_level = style_map.resolve_heading_level(record.style_id)
        return style_map
