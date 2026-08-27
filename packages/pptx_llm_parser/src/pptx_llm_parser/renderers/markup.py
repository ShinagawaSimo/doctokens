"""Small, shared serializer for the parser's line-oriented markup.

The renderer deliberately emits compact attributes, but an attribute must be
quoted whenever an unquoted output value would be ambiguous or unsafe. Keeping
that rule in one object prevents individual resource renderers from drifting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape as escape_text
from typing import Any


@dataclass
class AttributeBuilder:
    """Build escaped markup attributes with deterministic ordering."""

    _parts: list[str] = field(default_factory=list)

    def add(self, name: str, value: Any, *, omit_none: bool = True) -> AttributeBuilder:
        if value is None and omit_none:
            return self
        text = str(value)
        rendered = f'"{escape_text(text, quote=True)}"' if _needs_quotes(text) else escape_text(text, quote=False)
        self._parts.append(f" {name}={rendered}")
        return self

    def flag(self, name: str, enabled: bool = True) -> AttributeBuilder:
        if enabled:
            self._parts.append(f" {name}")
        return self

    def render(self) -> str:
        return "".join(self._parts)


def _needs_quotes(value: str) -> bool:
    # The compact output grammar rejects whitespace and these syntax
    # characters. Ampersands are quoted as well so entity-like text remains
    # literal in the parser's output format.
    return not value or any(char.isspace() or char in "\"'`=<>&" for char in value)
