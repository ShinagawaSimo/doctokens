"""Render the visible value of Word ``w:numFmt`` numbering formats.

The format names and their basic algorithms come from ISO/IEC 29500
17.18.59. Microsoft Word's documented deviations are applied here rather
than in the numbering state machine; this keeps counter advancement and
visible number conversion separate.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import ClassVar

from ...core.models import ParseWarning, append_warning
from .format_codes import (
    _AIUEO_FULL_WIDTH,
    _AIUEO_HALF_WIDTH,
    _APPLICATION_DEFINED_NFC_VALUES,
    _MAX_WORD_VALUE,
    _NFC_FORMATS,
    _WORD_LIMITED_FORMATS,
)
from .format_east_asian import EastAsianNumberRenderer
from .format_registry import _build_formatters
from .format_sequences import _decimal_ordinal, _roman, _word_cycled_sequence, _word_letter_sequence
from .format_words import _english_cardinal, _english_ordinal
from .language import cardinal_text, latin_alphabet, ordinal, ordinal_text


class NumberFormatRenderer:
    """Format one numbering value according to Word's ``ST_NumberFormat``."""

    _NFC_FORMATS: ClassVar[dict[int, str]] = _NFC_FORMATS

    def __init__(self, warnings: list[ParseWarning]) -> None:
        self._warnings = warnings
        self._warned_formats: set[str] = set()
        self._warned_custom_formats: set[str] = set()
        self._warned_nfc_values: set[int] = set()
        self._warned_ranges: set[tuple[str, int]] = set()
        self._formatters: Mapping[str, Callable[[int], str]] = MappingProxyType(
            _build_formatters(EastAsianNumberRenderer(self._out_of_range))
        )

    def format(
        self,
        value: int,
        number_format: str,
        language: str | None = None,
        custom_format: str | None = None,
    ) -> str:
        """Convert ``value`` to the text Word displays for ``number_format``."""
        if value > _MAX_WORD_VALUE:
            return ""
        if number_format in _WORD_LIMITED_FORMATS and value > 999_999:
            return self._out_of_range(value, number_format, display="")
        if number_format == "japaneseDigitalTenThousand" and value > 9_999:
            return self._out_of_range(value, number_format, display="")
        if number_format == "hex" and value > 65_535:
            return self._out_of_range(value, number_format, display="")
        if number_format == "koreanLegal" and value > 9_999_999:
            return self._out_of_range(value, number_format, display="")

        if custom_format:
            custom_value = self._format_custom(value, custom_format, language)
            if custom_value is not None:
                return custom_value
            self._warn_custom_format(custom_format, fallback=number_format)
        if number_format == "custom":
            if not custom_format:
                self._warn_custom_format(None, fallback="decimal")
            return str(value)
        if number_format == "cardinalText":
            return cardinal_text(value, language, _english_cardinal)
        if number_format == "ordinal":
            return ordinal(value, language, _decimal_ordinal)
        if number_format == "ordinalText":
            return ordinal_text(value, language, _english_ordinal)
        if number_format in {"upperLetter", "lowerLetter"}:
            alphabet = latin_alphabet(language, upper=number_format == "upperLetter")
            if alphabet is not None:
                return _word_letter_sequence(value, alphabet)

        formatter = self._formatters.get(number_format)
        if formatter is not None:
            return formatter(value)
        if number_format not in self._warned_formats:
            self._warned_formats.add(number_format)
            append_warning(
                self._warnings,
                "UNSUPPORTED_NUMBER_FORMAT",
                f"Unsupported numbering format {number_format!r}; decimal fallback is used.",
                part="word/numbering.xml",
            )
        return str(value)

    def format_from_nfc(self, value: int, nfc: int) -> str:
        """Format a ``numberingChange/@original`` NFC value."""
        number_format = _NFC_FORMATS.get(nfc)
        if number_format is not None:
            return self.format(value, number_format)
        if self.is_application_defined_nfc(nfc):
            self._warn_application_defined_nfc(nfc)
        else:
            self._warn_unknown_nfc(nfc)
        return ""

    @classmethod
    def is_application_defined_nfc(cls, nfc: int) -> bool:
        """Return whether MS-OI29500 permits an NFC value to be ignored."""
        return nfc in _APPLICATION_DEFINED_NFC_VALUES or nfc >= 60

    # Basic formats -----------------------------------------------------

    def _format_custom(self, value: int, pattern: str, language: str | None) -> str | None:
        """Render the XSLT format subset that Word numbering exposes."""
        if pattern == "ア":
            return _word_cycled_sequence(value, _AIUEO_FULL_WIDTH)
        if pattern == "ｱ":
            return _word_cycled_sequence(value, _AIUEO_HALF_WIDTH)
        if not pattern:
            return None
        token_match = next(
            (match for match in re.finditer(r"[A-Za-z0-9]+", pattern) if set(match.group(0)) <= {"0", "1", "A", "a", "I", "i"}),
            None,
        )
        if token_match is None:
            return None
        token = token_match.group(0)
        if set(token) <= {"0", "1"} and "1" in token:
            rendered = str(value).zfill(len(token))
        elif set(token) == {"A"}:
            rendered = _word_letter_sequence(value, latin_alphabet(language, upper=True) or "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        elif set(token) == {"a"}:
            rendered = _word_letter_sequence(value, latin_alphabet(language, upper=False) or "abcdefghijklmnopqrstuvwxyz")
        elif set(token) == {"I"}:
            rendered = _roman(value)
        elif set(token) == {"i"}:
            rendered = _roman(value).lower()
        else:
            return None
        return pattern[: token_match.start()] + rendered + pattern[token_match.end() :]

    def _warn_custom_format(self, pattern: str | None, *, fallback: str) -> None:
        key = f"{pattern!r}:{fallback}"
        if key in self._warned_custom_formats:
            return
        self._warned_custom_formats.add(key)
        description = "is missing" if pattern is None else f"{pattern!r} is not supported"
        append_warning(
            self._warnings,
            "UNSUPPORTED_CUSTOM_NUMBER_FORMAT",
            f"Custom numbering format {description}; {fallback} is used instead.",
            part="word/numbering.xml",
        )

    def _warn_application_defined_nfc(self, nfc: int) -> None:
        if nfc in self._warned_nfc_values:
            return
        self._warned_nfc_values.add(nfc)
        append_warning(
            self._warnings,
            "APPLICATION_DEFINED_NUMBER_FORMAT",
            f"Application-defined numberingChange NFC value {nfc} was ignored.",
            part="word/document.xml",
        )

    def _warn_unknown_nfc(self, nfc: int) -> None:
        if nfc in self._warned_nfc_values:
            return
        self._warned_nfc_values.add(nfc)
        append_warning(
            self._warnings,
            "INVALID_NUMBERING_CHANGE",
            f"Unknown numberingChange NFC value {nfc} was ignored.",
            part="word/document.xml",
        )

    # Range diagnostics -------------------------------------------------

    def _out_of_range(self, value: int, number_format: str, *, display: str) -> str:
        key = (number_format, value)
        if key not in self._warned_ranges:
            self._warned_ranges.add(key)
            append_warning(
                self._warnings,
                "NUMBERING_VALUE_OUT_OF_RANGE",
                f"Word does not display numbering value {value} for {number_format}.",
                part="word/numbering.xml",
            )
        return display


__all__ = ["NumberFormatRenderer"]
