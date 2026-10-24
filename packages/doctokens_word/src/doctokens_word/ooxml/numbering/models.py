"""Immutable records shared by numbering parsing and rendering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ...core.models import RunFormat


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
    marker_font: str | None = None
    picture_bullet_id: str | None = None
    restart_level: int | None = None
    is_legal: bool = False
    language: str | None = None
    custom_format: str | None = None


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


def bullet_symbol(template: str | None, marker_font: str | None = None) -> str:
    """Resolve known Symbol/Wingdings private-use bullets to Unicode."""
    if not template:
        return "•"
    symbols = {
        "\uf06c": "●",
        "\uf06e": "■",
        "\uf075": "◆",
        "\uf0b7": "•",
        "\uf0a7": "▪",
        "\uf0fc": "✓",
        "\uf0fd": "✓",
        "\uf0fe": "✕",
    }
    font_symbols = {
        "symbol": {"\uf0b7": "•", "\uf0a7": "▪", "\uf06c": "●", "\uf06e": "■", "\uf075": "◆"},
        "wingdings": {"\uf0a7": "▪", "\uf0b7": "•", "\uf0fc": "✓", "\uf0fd": "✓", "\uf0fe": "✕"},
        "wingdings 2": {"\uf0a7": "▪", "\uf0fc": "✓", "\uf0fe": "✕"},
        "wingdings 3": {"\uf0fc": "✓", "\uf0fe": "✕"},
    }
    font_key = (marker_font or "").strip().lower()
    resolved = font_symbols.get(font_key, {})
    return "".join(resolved.get(char, symbols.get(char, "•" if 0xE000 <= ord(char) <= 0xF8FF else char)) for char in template)


__all__ = ["NumberingInstance", "NumberingLevel", "bullet_symbol"]
