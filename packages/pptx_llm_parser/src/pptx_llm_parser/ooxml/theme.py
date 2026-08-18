"""Theme part parsing — color scheme with Office default fallback."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.relationships import RelationshipIndex

from ..core.constants import local_name
from ..core.package import PackageReader

THEME_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
PRESENTATION_PART = "ppt/presentation.xml"

_THEME_SLOTS = (
    "dk1",
    "lt1",
    "dk2",
    "lt2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
)

# Office default theme colors (fallback when theme1.xml is absent) — same
# values the xlsx FormatIndex uses.
_DEFAULT_THEME: dict[str, str] = {
    "dk1": "#000000",
    "lt1": "#FFFFFF",
    "dk2": "#44546A",
    "lt2": "#E7E6E6",
    "accent1": "#4472C4",
    "accent2": "#ED7D31",
    "accent3": "#A5A5A5",
    "accent4": "#FFC000",
    "accent5": "#5B9BD5",
    "accent6": "#70AD47",
    "hlink": "#0563C1",
    "folHlink": "#954F72",
}


class ThemeParser:
    """Resolve the deck's clrScheme into slot name → #RRGGBB."""

    def __init__(
        self,
        pkg: PackageReader,
        relationships: RelationshipIndex,
        warnings: list[ParseWarning],
    ) -> None:
        self._pkg = pkg
        self._relationships = relationships
        self._warnings = warnings
        self._cache: dict[str, dict[str, str]] = {}

    def parse(self) -> dict[str, str]:
        part: str | None = None
        locator = PRESENTATION_PART
        theme_records = list(self._relationships.by_type(THEME_REL_TYPE))
        # Some producers attach the theme only to a slide master. Prefer the
        # presentation-level relationship, then choose the first master theme
        # in deterministic relationship order.
        preferred = [record for record in theme_records if record.source_part == PRESENTATION_PART]
        preferred.extend(
            record for record in theme_records if record.source_part.startswith("ppt/slideMasters/") and record not in preferred
        )
        if preferred:
            part = preferred[0].resolved_target
            locator = preferred[0].source_part
        if part is None:
            self._warnings.append(
                ParseWarning(
                    code="THEME_PART_MISSING",
                    message="Theme relationship missing",
                    locator=locator,
                )
            )
            return dict(_DEFAULT_THEME)
        return self._parse_part(part, locator)

    def parse_for_source(self, source_part: str) -> dict[str, str]:
        """Resolve the theme related to a slide master, with deck fallback."""
        records = self._relationships.by_type(THEME_REL_TYPE, source_part=source_part)
        for record in records:
            if record.resolved_target is not None:
                return self._parse_part(record.resolved_target, source_part)
        return self.parse()

    def _parse_part(self, part: str, locator: str) -> dict[str, str]:
        cached = self._cache.get(part)
        if cached is not None:
            return dict(cached)
        if not self._pkg.exists(part):
            self._warnings.append(
                ParseWarning(
                    code="THEME_PART_MISSING",
                    message=f"Theme part missing: {part}",
                    locator=locator,
                )
            )
            fallback = dict(_DEFAULT_THEME)
            self._cache[part] = fallback
            return dict(fallback)
        try:
            root = self._read_xml(part)
        except ET.ParseError as exc:
            self._warnings.append(ParseWarning(code="THEME_XML_INVALID", message=f"Invalid theme XML: {exc}", locator=part))
            fallback = dict(_DEFAULT_THEME)
            self._cache[part] = fallback
            return dict(fallback)
        scheme = self._find_descendant(root, "clrScheme")
        if scheme is None:
            self._warnings.append(
                ParseWarning(
                    code="THEME_MISSING_CLRSCHEME",
                    message="a:theme without a:clrScheme",
                    locator=part,
                )
            )
            fallback = dict(_DEFAULT_THEME)
            self._cache[part] = fallback
            return dict(fallback)
        colors: dict[str, str] = {}
        for slot in _THEME_SLOTS:
            colors[slot] = _DEFAULT_THEME.get(slot, "#000000")
            for child in scheme:
                if local_name(child.tag) != slot:
                    continue
                value = self._slot_value(child)
                if value:
                    colors[slot] = value
        self._cache[part] = colors
        return dict(colors)

    @staticmethod
    def _slot_value(slot_element: ET.Element) -> str | None:
        for child in slot_element:
            name = local_name(child.tag)
            if name == "srgbClr":
                raw = child.get("val")
            elif name == "sysClr":
                raw = child.get("lastClr")
            else:
                continue
            if raw and len(raw) == 6:
                return "#" + raw.upper()
        return None

    @staticmethod
    def _find_descendant(element: ET.Element, local: str) -> ET.Element | None:
        for descendant in element.iter():
            if local_name(descendant.tag) == local:
                return descendant
        return None

    def _read_xml(self, part: str) -> ET.Element:
        with self._pkg.open_entry(part) as stream:
            return ET.parse(stream).getroot()
