"""Numbering counter state and visible label materialization."""

from __future__ import annotations

import re
from collections.abc import Mapping

from ...core.models import NumberingLabel, ParseWarning, append_warning
from .formats import NumberFormatRenderer
from .models import NumberingLevel, bullet_symbol
from .parser import NumberingMap


class NumberingState:
    """Maintain one document's list counters and render visible labels."""

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
        level_overrides: Mapping[int, NumberingLevel] | None = None,
    ) -> NumberingLabel | None:
        level = self._level_for(num_id, numbering_level, level_overrides)
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
        self._reset_deeper_levels(num_id, numbering_level, counters, level_overrides)
        label = self._render_label(num_id, numbering_level, counters, level_overrides)
        visible_text = "" if level.number_format == "none" or level.picture_bullet_id else label + self._suffix_text(level.suffix)
        result: NumberingLabel = {
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
        if level.marker_font:
            result["markerFont"] = level.marker_font
        return result

    def _level_for(
        self,
        num_id: str,
        numbering_level: int,
        level_overrides: Mapping[int, NumberingLevel] | None,
    ) -> NumberingLevel | None:
        if level_overrides is not None and numbering_level in level_overrides:
            return level_overrides[numbering_level]
        return self.numbering.level_for(num_id, numbering_level)

    def _reset_deeper_levels(
        self,
        num_id: str,
        used_level: int,
        counters: dict[int, int],
        level_overrides: Mapping[int, NumberingLevel] | None,
    ) -> None:
        for deeper_level in list(counters):
            deeper = self._level_for(num_id, deeper_level, level_overrides)
            if deeper_level > used_level and deeper is not None and self._restarts_after(deeper, used_level, deeper_level):
                del counters[deeper_level]

    @staticmethod
    def _restarts_after(deeper: NumberingLevel, used_level: int, deeper_level: int) -> bool:
        if deeper.restart_level == 0:
            return False
        restart_boundary = deeper_level - 1 if deeper.restart_level is None else deeper.restart_level - 1
        return used_level <= restart_boundary

    def _render_label(
        self,
        num_id: str,
        numbering_level: int,
        counters: dict[int, int],
        level_overrides: Mapping[int, NumberingLevel] | None,
    ) -> str:
        current_level = self._level_for(num_id, numbering_level, level_overrides)
        if current_level is None or current_level.number_format == "none" or current_level.picture_bullet_id:
            return ""
        template = current_level.level_text
        if not template:
            if current_level.number_format == "bullet" and not current_level.is_legal:
                return "•"
            return self._format_number(
                counters[numbering_level],
                self._format_for(current_level, current_level),
                current_level.language,
                current_level.custom_format,
            )
        if current_level.number_format == "bullet":
            if current_level.is_legal:
                return self._format_number(counters[numbering_level], "decimal")
            return bullet_symbol(template, current_level.marker_font)

        def replace_match(match: re.Match[str]) -> str:
            if match.group(0) == "%%":
                return "%"
            reference_level = int(match.group(1)) - 1
            reference = self._level_for(num_id, reference_level, level_overrides) or current_level
            if reference.number_format == "none":
                return ""
            value = counters.get(reference_level, reference.start)
            return self._format_number(
                value,
                self._format_for(current_level, reference),
                reference.language,
                reference.custom_format,
            )

        return re.sub(r"%%|%([1-9][0-9]*)", replace_match, template)

    @staticmethod
    def _format_for(current_level: NumberingLevel, reference_level: NumberingLevel) -> str:
        return "decimal" if current_level.is_legal else reference_level.number_format

    def _format_number(
        self,
        value: int,
        number_format: str,
        language: str | None = None,
        custom_format: str | None = None,
    ) -> str:
        return self._number_formatter.format(value, number_format, language, custom_format)

    @staticmethod
    def _suffix_text(suffix: str) -> str:
        if suffix == "nothing":
            return ""
        if suffix == "space":
            return " "
        return "\t"

    _chinese_counting = staticmethod(NumberFormatRenderer._chinese_counting)
    _chinese_digital = staticmethod(NumberFormatRenderer._chinese_digital)

    @staticmethod
    def _japanese_counting(value: int) -> str:
        return NumberFormatRenderer([]).format(value, "japaneseCounting")


__all__ = ["NumberingState"]
