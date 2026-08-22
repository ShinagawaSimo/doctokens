"""Parse Word numbering definitions and materialize visible paragraph markers."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from types import MappingProxyType
from xml.etree import ElementTree as ET

from ..core.constants import attr, child_elements, first_child, is_on, qualified_name
from ..core.models import NumberingLabel, ParseWarning, RunFormat, append_warning
from ..core.package import PackageReader
from .formatting import parse_run_format
from .number_formats import NumberFormatRenderer


@dataclass(frozen=True)
class NumberingLevel:
    """Display rules for one zero-based ``w:lvl`` definition."""

    numbering_level: int
    start: int = 1
    number_format: str = "decimal"
    level_text: str | None = None
    suffix: str = "tab"
    paragraph_style_id: str | None = None
    marker_format: RunFormat = field(default_factory=dict)
    picture_bullet_id: str | None = None
    restart_level: int | None = None
    is_legal: bool = False


@dataclass(frozen=True)
class NumberingInstance:
    """A concrete ``w:num`` instance and its level-local overrides."""

    numbering_id: str
    abstract_num_id: str
    level_overrides: Mapping[int, NumberingLevel] = field(default_factory=dict)
    start_overrides: Mapping[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "level_overrides", MappingProxyType(dict(self.level_overrides)))
        object.__setattr__(self, "start_overrides", MappingProxyType(dict(self.start_overrides)))


class NumberingMap:
    """Immutable numbering-definition index; counters live in ``NumberingState``."""

    def __init__(
        self,
        abstract_levels: dict[str, dict[int, NumberingLevel]],
        instances: dict[str, NumberingInstance],
        warnings: list[ParseWarning],
        picture_bullet_relationships: Mapping[str, str] | None = None,
        style_link_num_ids: Mapping[str, str] | None = None,
    ) -> None:
        self.abstract_levels: Mapping[str, Mapping[int, NumberingLevel]] = MappingProxyType(
            {abstract_id: MappingProxyType(dict(levels)) for abstract_id, levels in abstract_levels.items()}
        )
        self.instances: Mapping[str, NumberingInstance] = MappingProxyType(dict(instances))
        self.picture_bullet_relationships: Mapping[str, str] = MappingProxyType(dict(picture_bullet_relationships or {}))
        self.style_link_num_ids: Mapping[str, str] = MappingProxyType(dict(style_link_num_ids or {}))
        self.warnings = warnings

    def picture_bullet_relationship(self, picture_bullet_id: str | None) -> str | None:
        """Return the relationship used by an optional ``w:lvlPicBulletId``."""
        return self.picture_bullet_relationships.get(picture_bullet_id or "")

    def level_for(self, num_id: str, numbering_level: int) -> NumberingLevel | None:
        """Resolve an effective level, including overrides and style links."""
        return self._level_for(num_id, numbering_level, visited=set())

    def _level_for(self, num_id: str, numbering_level: int, visited: set[str]) -> NumberingLevel | None:
        if num_id in visited:
            return None
        visited.add(num_id)
        instance = self.instances.get(num_id)
        if instance is None:
            return None

        override = instance.level_overrides.get(numbering_level)
        if override is not None:
            return self._with_start_override(instance, numbering_level, override)

        linked_num_id = self.style_link_num_ids.get(instance.abstract_num_id)
        if linked_num_id and linked_num_id != num_id:
            linked_level = self._level_for(linked_num_id, numbering_level, visited)
            if linked_level is not None:
                return self._with_start_override(instance, numbering_level, linked_level)

        base = self.abstract_levels.get(instance.abstract_num_id, {}).get(numbering_level)
        return self._with_start_override(instance, numbering_level, base)

    @staticmethod
    def _with_start_override(
        instance: NumberingInstance,
        numbering_level: int,
        level: NumberingLevel | None,
    ) -> NumberingLevel | None:
        if level is None:
            return None
        start = instance.start_overrides.get(numbering_level)
        return replace(level, start=start) if start is not None else level

    def level_for_style(self, num_id: str, style_id: str) -> int | None:
        """Resolve a level bound to a paragraph style, following style-number links."""
        pending = [num_id]
        visited: set[str] = set()
        while pending:
            current_num_id = pending.pop()
            if current_num_id in visited:
                continue
            visited.add(current_num_id)
            instance = self.instances.get(current_num_id)
            if instance is None:
                continue

            for level, override in instance.level_overrides.items():
                if override.paragraph_style_id == style_id:
                    return level
            for level in sorted(self.abstract_levels.get(instance.abstract_num_id, {})):
                if level in instance.level_overrides:
                    continue
                definition: NumberingLevel | None = self.level_for(current_num_id, level)
                if definition is not None and definition.paragraph_style_id == style_id:
                    return level
            linked_num_id = self.style_link_num_ids.get(instance.abstract_num_id)
            if linked_num_id:
                pending.append(linked_num_id)
        return None

    def to_debug_dict(self) -> dict[str, object]:
        """Produce a JSON-ready view of source numbering definitions."""
        return {
            "abstractNums": {
                abstract_id: {str(level): asdict(definition) for level, definition in sorted(levels.items())}
                for abstract_id, levels in sorted(self.abstract_levels.items())
            },
            "nums": {
                num_id: {
                    "numId": instance.numbering_id,
                    "abstractNumId": instance.abstract_num_id,
                    "levelOverrides": {
                        str(level): asdict(definition) for level, definition in sorted(instance.level_overrides.items())
                    },
                    "startOverrides": {str(level): start for level, start in sorted(instance.start_overrides.items())},
                }
                for num_id, instance in sorted(self.instances.items())
            },
            "pictureBullets": dict(sorted(self.picture_bullet_relationships.items())),
            "styleLinks": dict(sorted(self.style_link_num_ids.items())),
        }


class NumberingState:
    """Maintain one document's list counters and turn levels into visible labels."""

    def __init__(self, numbering: NumberingMap, warnings: list[ParseWarning]) -> None:
        self.numbering = numbering
        self.warnings = warnings
        self._counters: dict[str, dict[int, int]] = {}
        self._number_formatter = NumberFormatRenderer(warnings)

    def advance(
        self,
        num_id: str,
        numbering_level: int,
        *,
        part: str | None = None,
        block_id: str | None = None,
    ) -> NumberingLabel | None:
        """Advance a list level and return its synthetic visible run metadata."""
        level = self.numbering.level_for(num_id, numbering_level)
        if level is None:
            append_warning(
                self.warnings,
                "NUMBERING_LEVEL_MISSING",
                f"Missing numbering level for numId={num_id}, numbering_level={numbering_level}",
                part=part,
                block_id=block_id,
            )
            return None

        counters = self._counters.setdefault(num_id, {})
        counters[numbering_level] = counters.get(numbering_level, level.start - 1) + 1
        self._reset_deeper_levels(num_id, numbering_level, counters)

        label = self._render_label(num_id, numbering_level, counters)
        visible_text = "" if level.number_format == "none" or level.picture_bullet_id else label + self._suffix_text(level.suffix)
        return {
            "numId": num_id,
            "level": numbering_level,
            "label": label,
            "text": visible_text,
            "format": level.number_format,
            "template": level.level_text,
            "suffix": level.suffix,
            "counter": counters[numbering_level],
            "markerFormat": level.marker_format,
            "pictureBulletId": level.picture_bullet_id,
            "markerImageId": None,
            "legal": level.is_legal,
        }

    def _reset_deeper_levels(self, num_id: str, used_level: int, counters: dict[int, int]) -> None:
        for deeper_level in list(counters):
            deeper = self.numbering.level_for(num_id, deeper_level)
            if deeper_level > used_level and deeper is not None and self._restarts_after(deeper, used_level, deeper_level):
                del counters[deeper_level]

    @staticmethod
    def _restarts_after(deeper: NumberingLevel, used_level: int, deeper_level: int) -> bool:
        """Return whether the current higher-level item restarts ``deeper``."""
        if deeper.restart_level == 0:
            return False
        restart_boundary = deeper_level - 1 if deeper.restart_level is None else deeper.restart_level - 1
        return used_level <= restart_boundary

    def _render_label(self, num_id: str, numbering_level: int, counters: dict[int, int]) -> str:
        current_level = self.numbering.level_for(num_id, numbering_level)
        if current_level is None or current_level.number_format == "none" or current_level.picture_bullet_id:
            return ""
        template = current_level.level_text
        if not template:
            if current_level.number_format == "bullet" and not current_level.is_legal:
                return "•"
            return self._format_number(counters[numbering_level], self._format_for(current_level, current_level))
        if current_level.number_format == "bullet" and "%" not in template:
            return self._format_number(counters[numbering_level], "decimal") if current_level.is_legal else template

        def replace_match(match: re.Match[str]) -> str:
            if match.group(0) == "%%":
                return "%"
            reference_level = int(match.group(1)) - 1
            reference = self.numbering.level_for(num_id, reference_level) or current_level
            if reference.number_format == "none":
                return ""
            value = counters.get(reference_level, reference.start)
            return self._format_number(value, self._format_for(current_level, reference))

        return re.sub(r"%%|%([1-9])", replace_match, template)

    @staticmethod
    def _format_for(current_level: NumberingLevel, reference_level: NumberingLevel) -> str:
        return "decimal" if current_level.is_legal else reference_level.number_format

    def _format_number(self, value: int, number_format: str) -> str:
        return self._number_formatter.format(value, number_format)

    @staticmethod
    def _bullet_symbol(template: str | None) -> str:
        """Map common Symbol-font private-use bullets without retaining font metadata."""
        if not template:
            return "•"
        return {"\uf06c": "●", "\uf06e": "■", "\uf075": "◆"}.get(template, template)

    @staticmethod
    def _suffix_text(suffix: str) -> str:
        if suffix == "nothing":
            return ""
        if suffix == "space":
            return " "
        return "\t"

    # Kept as small compatibility helpers for direct unit tests and callers.
    _chinese_counting = staticmethod(NumberFormatRenderer._chinese_counting)
    _chinese_digital = staticmethod(NumberFormatRenderer._chinese_digital)
    _japanese_counting = staticmethod(NumberFormatRenderer._japanese_counting)


class NumberingParser:
    """Read ``word/numbering.xml`` into immutable definition records."""

    def __init__(
        self,
        package: PackageReader,
        warnings: list[ParseWarning],
        numbering_style_num_ids: Mapping[str, str] | None = None,
    ) -> None:
        self.package = package
        self.warnings = warnings
        self.numbering_style_num_ids = numbering_style_num_ids or {}

    def parse(self) -> NumberingMap:
        if not self.package.exists("word/numbering.xml"):
            return NumberingMap({}, {}, self.warnings)
        with self.package.open_entry("word/numbering.xml") as stream:
            root = ET.parse(stream).getroot()

        picture_bullet_relationships = self._parse_picture_bullet_relationships(root)
        abstract_levels, style_link_num_ids = self._parse_abstract_numbers(root)
        instances = self._parse_instances(root)
        return NumberingMap(
            abstract_levels,
            instances,
            self.warnings,
            picture_bullet_relationships,
            style_link_num_ids,
        )

    def _parse_abstract_numbers(self, root: ET.Element) -> tuple[dict[str, dict[int, NumberingLevel]], dict[str, str]]:
        abstract_levels: dict[str, dict[int, NumberingLevel]] = {}
        style_link_num_ids: dict[str, str] = {}
        for abstract_num in child_elements(root, "w", "abstractNum"):
            abstract_id = attr(abstract_num, "w", "abstractNumId")
            if not abstract_id:
                continue
            style_id = self._child_attr(abstract_num, "numStyleLink", "val")
            linked_num_id = self.numbering_style_num_ids.get(style_id or "")
            if linked_num_id:
                style_link_num_ids[abstract_id] = linked_num_id
            levels: dict[int, NumberingLevel] = {}
            for level_element in child_elements(abstract_num, "w", "lvl"):
                level = self._parse_level(level_element)
                if level is not None:
                    levels[level.numbering_level] = level
            abstract_levels[abstract_id] = levels
        return abstract_levels, style_link_num_ids

    def _parse_instances(self, root: ET.Element) -> dict[str, NumberingInstance]:
        instances: dict[str, NumberingInstance] = {}
        for num in child_elements(root, "w", "num"):
            num_id = attr(num, "w", "numId")
            abstract_id = self._child_attr(num, "abstractNumId", "val")
            if not num_id or not abstract_id:
                continue
            level_overrides: dict[int, NumberingLevel] = {}
            start_overrides: dict[int, int] = {}
            for override in child_elements(num, "w", "lvlOverride"):
                level_index = self._parse_int(attr(override, "w", "ilvl"), 0)
                assert level_index is not None
                start = self._parse_int(self._child_attr(override, "startOverride", "val"))
                if start is not None:
                    start_overrides[level_index] = start
                definition = self._parse_level(first_child(override, "w", "lvl"))
                if definition is not None:
                    # ``lvlOverride`` owns the target level; its embedded ``lvl``
                    # cannot define restart behavior or redirect that target.
                    level_overrides[level_index] = replace(definition, numbering_level=level_index, restart_level=None)
            instances[num_id] = NumberingInstance(num_id, abstract_id, level_overrides, start_overrides)
        return instances

    def _parse_level(self, lvl: ET.Element | None) -> NumberingLevel | None:
        if lvl is None:
            return None
        level_value = self._parse_int(attr(lvl, "w", "ilvl"), 0)
        start = self._parse_int(self._child_attr(lvl, "start", "val"), 1)
        assert level_value is not None and start is not None
        number_format = self._child_attr(lvl, "numFmt", "val") or "decimal"
        level_text = self._child_attr(lvl, "lvlText", "val")
        return NumberingLevel(
            numbering_level=level_value,
            start=start,
            number_format=number_format,
            level_text=NumberingState._bullet_symbol(level_text) if number_format == "bullet" else level_text,
            suffix=self._child_attr(lvl, "suff", "val") or "tab",
            paragraph_style_id=self._child_attr(lvl, "pStyle", "val"),
            marker_format=parse_run_format(first_child(lvl, "w", "rPr")),
            picture_bullet_id=self._child_attr(lvl, "lvlPicBulletId", "val"),
            restart_level=self._parse_int(self._child_attr(lvl, "lvlRestart", "val")),
            is_legal=is_on(first_child(lvl, "w", "isLgl")),
        )

    @staticmethod
    def _parse_picture_bullet_relationships(root: ET.Element) -> dict[str, str]:
        relationships: dict[str, str] = {}
        image_data_tag = qualified_name("v", "imagedata")
        for picture_bullet in child_elements(root, "w", "numPicBullet"):
            picture_id = attr(picture_bullet, "w", "numPicBulletId")
            if not picture_id:
                continue
            for node in picture_bullet.iter(image_data_tag):
                relationship_id = attr(node, "r", "id")
                if relationship_id:
                    relationships[picture_id] = relationship_id
                    break
        return relationships

    @staticmethod
    def _child_attr(node: ET.Element, child_name: str, attr_name: str) -> str | None:
        child = first_child(node, "w", child_name)
        return attr(child, "w", attr_name) if child is not None else None

    @staticmethod
    def _parse_int(value: str | None, default: int | None = None) -> int | None:
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default
