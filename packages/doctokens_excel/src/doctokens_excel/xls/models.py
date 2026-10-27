"""Immutable basic XLS content, without an OOXML package projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from doctokens_core.containers.cfb import CfbLimits
from doctokens_core.contracts.models import ParseWarning


class XlsError(ValueError):
    """Malformed, unsupported or over-budget BIFF input."""


@dataclass(frozen=True, slots=True)
class XlsLimits:
    cfb: CfbLimits = field(default_factory=CfbLimits)
    max_sheets: int = 256
    max_records: int = 1_000_000
    max_strings: int = 500_000
    max_string_characters: int = 32_767
    max_total_string_characters: int = 16_000_000
    max_cells: int = 500_000
    max_xfs: int = 4096

    def __post_init__(self) -> None:
        for name in (
            "max_sheets",
            "max_records",
            "max_strings",
            "max_string_characters",
            "max_total_string_characters",
            "max_cells",
            "max_xfs",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class XlsCell:
    row: int
    column: int
    kind: Literal["string", "number", "boolean", "error"]
    value: str | float | bool
    xf_index: int
    from_formula: bool = False
    display_text: str | None = None

    @property
    def ref(self) -> str:
        column = self.column
        letters = ""
        while column:
            column, digit = divmod(column - 1, 26)
            letters = chr(65 + digit) + letters
        return f"{letters}{self.row}"


@dataclass(frozen=True, slots=True)
class XlsSheet:
    name: str
    state: Literal["visible", "hidden", "veryHidden"]
    cells: tuple[XlsCell, ...]


@dataclass(frozen=True, slots=True)
class XlsContent:
    sheets: tuple[XlsSheet, ...]
    date_1904: bool
    warnings: tuple[ParseWarning, ...] = ()
