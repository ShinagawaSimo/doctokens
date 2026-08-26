"""Parse ``word/numbering.xml`` into resolved numbering definitions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from xml.etree import ElementTree as ET

from ...core.constants import attr, child_elements, first_child, is_on, qualified_name
from ...core.models import ParseWarning
from ...core.package import PackageReader
from ..formatting import parse_run_format
from .models import NumberingInstance, NumberingLevel


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
        return self.picture_bullet_relationships.get(picture_bullet_id or "")

    def level_for(self, num_id: str, numbering_level: int) -> NumberingLevel | None:
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
                definition = self.level_for(current_num_id, level)
                if definition is not None and definition.paragraph_style_id == style_id:
                    return level
            linked_num_id = self.style_link_num_ids.get(instance.abstract_num_id)
            if linked_num_id:
                pending.append(linked_num_id)
        return None

class NumberingParser:
    """Read Word's numbering part and resolve level-local overrides."""

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
        root = self.package.read_xml("word/numbering.xml")
        picture_bullet_relationships = self._parse_picture_bullet_relationships(root)
        abstract_levels, style_link_num_ids = self._parse_abstract_numbers(root)
        instances = self._parse_instances(root)
        return NumberingMap(abstract_levels, instances, self.warnings, picture_bullet_relationships, style_link_num_ids)

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
                    level_overrides[level_index] = replace(definition, numbering_level=level_index, restart_level=None)
            instances[num_id] = NumberingInstance(num_id, abstract_id, level_overrides, start_overrides)
        return instances

    def _parse_level(self, lvl: ET.Element | None) -> NumberingLevel | None:
        if lvl is None:
            return None
        level_value = self._parse_int(attr(lvl, "w", "ilvl"), 0)
        start = self._parse_int(self._child_attr(lvl, "start", "val"), 1)
        assert level_value is not None and start is not None
        num_fmt = first_child(lvl, "w", "numFmt")
        number_format = (attr(num_fmt, "w", "val") if num_fmt is not None else None) or "decimal"
        custom_format = attr(num_fmt, "w", "format") if num_fmt is not None else None
        level_text = self._child_attr(lvl, "lvlText", "val")
        run_properties = first_child(lvl, "w", "rPr")
        return NumberingLevel(
            numbering_level=level_value,
            start=start,
            number_format=number_format,
            level_text=level_text,
            suffix=self._child_attr(lvl, "suff", "val") or "tab",
            paragraph_style_id=self._child_attr(lvl, "pStyle", "val"),
            marker_format=parse_run_format(run_properties),
            marker_font=self._run_font(run_properties),
            picture_bullet_id=self._child_attr(lvl, "lvlPicBulletId", "val"),
            restart_level=self._parse_int(self._child_attr(lvl, "lvlRestart", "val")),
            is_legal=is_on(first_child(lvl, "w", "isLgl")),
            language=self._run_language(run_properties),
            custom_format=custom_format,
        )

    @classmethod
    def _run_language(cls, run_properties: ET.Element | None) -> str | None:
        if run_properties is None:
            return None
        language = cls._child_attr(run_properties, "lang", "val")
        return language or cls._child_attr(run_properties, "lang", "eastAsia")

    @classmethod
    def _run_font(cls, run_properties: ET.Element | None) -> str | None:
        if run_properties is None:
            return None
        fonts = first_child(run_properties, "w", "rFonts")
        if fonts is None:
            return None
        for name in ("ascii", "hAnsi", "eastAsia", "cs"):
            value = attr(fonts, "w", name)
            if value:
                return value
        return None

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


__all__ = ["NumberingMap", "NumberingParser"]
