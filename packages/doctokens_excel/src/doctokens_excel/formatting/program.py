"""Workbook-owned format syntax; values and rendered cells are never cached."""

from __future__ import annotations

from .codes import _date_scan_text, resolve_format
from .date_context import date_context
from .date_program import DateProgram, compile_date
from .decimal import DecimalPattern, compile_decimal_pattern
from .sections import (
    SectionDirectives,
    _condition_matches,
    _section_directives,
    _split_format_sections,
    balanced_format,
    directive_values,
    supported_directives,
)

_COLORS = {
    "black": "#000000",
    "blue": "#0000FF",
    "cyan": "#00FFFF",
    "green": "#008000",
    "magenta": "#FF00FF",
    "red": "#FF0000",
    "white": "#FFFFFF",
    "yellow": "#FFFF00",
}


class FormatProgram:
    def __init__(self, code: str, locale: str) -> None:
        self.code = code
        self.locale = locale
        self.sections = _split_format_sections(code)
        self.supported = balanced_format(code) and len(self.sections) <= 4 and all(supported_directives(s) for s in self.sections)
        self.directives = {section: _section_directives(section) for section in self.sections}
        self.conditional = any(self.directives[section].conditions for section in self.sections[:3])
        self._classifications: dict[str, tuple[bool, bool]] = {}
        self._syntax: dict[str, str] = {}
        self._dates: dict[str, DateProgram] = {}
        self._decimals: dict[str, DecimalPattern] = {}
        self.colors = {
            section: next(
                (_COLORS[value.lower()] for value in directive_values(section) if value.lower() in _COLORS),
                None,
            )
            for section in self.sections
        }

    def select(self, value: float) -> tuple[str | None, float]:
        sections = self.sections[:3]
        if self.conditional:
            for section in sections:
                conditions = self.directives[section].conditions
                if not conditions or all(_condition_matches(value, condition) for condition in conditions):
                    return section, value
            return None, value
        if len(sections) == 1:
            return sections[0], value
        if value < 0:
            return sections[1], abs(value)
        if len(sections) == 2 or value > 0:
            return sections[0], value
        return sections[2], value

    def classify(self, section: str) -> tuple[bool, bool]:
        if section not in self._classifications:
            self._classifications[section] = resolve_format(0, section, self.locale)
        return self._classifications[section]

    def syntax(self, section: str) -> str:
        if section not in self._syntax:
            self._syntax[section] = _date_scan_text(section)
        return self._syntax[section]

    def date(self, section: str) -> DateProgram:
        if section not in self._dates:
            self._dates[section] = compile_date(date_context(section, self.locale))
        return self._dates[section]

    def decimal(self, core: str) -> DecimalPattern:
        if core not in self._decimals:
            self._decimals[core] = compile_decimal_pattern(core)
        return self._decimals[core]

    def section_directives(self, section: str) -> SectionDirectives:
        return self.directives[section]
