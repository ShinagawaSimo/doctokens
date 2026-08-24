"""Decode Word's revision-time ``w:numberingChange`` representation."""

from __future__ import annotations

import re

from ...core.models import ParseWarning, append_warning
from .formats import NumberFormatRenderer
from .models import NumberingLevel


def parse_numbering_change(
    original: str | None,
    warnings: list[ParseWarning],
    *,
    part: str | None = None,
    block_id: str | None = None,
) -> dict[int, NumberingLevel]:
    """Decode Word's ``%level:nfc:format:separator`` definitions."""
    if not original:
        return {}

    definition_pattern = re.compile(r"(?<!%)%([0-9]+):([0-9]+):([^:]+):")
    definitions: list[tuple[re.Match[str], str]] = []
    search_from = 0
    while True:
        match = definition_pattern.search(original, search_from)
        if match is None:
            break
        next_match = definition_pattern.search(original, match.end())
        separator_end = next_match.start() if next_match is not None else len(original)
        definitions.append((match, original[match.end() : separator_end]))
        search_from = match.end()

    if not definitions:
        append_warning(
            warnings,
            "INVALID_NUMBERING_CHANGE",
            "The numberingChange original value contains no valid level definition.",
            part=part,
            block_id=block_id,
        )
        return {}

    first_prefix = original[: definitions[0][0].start()]
    levels: dict[int, NumberingLevel] = {}
    significant_length = len(first_prefix.replace("%%", "%"))
    for match, separator in definitions:
        level_number = int(match.group(1))
        nfc = int(match.group(2))
        format_name = match.group(3)
        mapped_format = NumberFormatRenderer._NFC_FORMATS.get(nfc)
        if mapped_format is None:
            warning_code = (
                "APPLICATION_DEFINED_NUMBER_FORMAT"
                if NumberFormatRenderer.is_application_defined_nfc(nfc)
                else "INVALID_NUMBERING_CHANGE"
            )
            message = (
                f"Application-defined numberingChange NFC value {nfc} was ignored."
                if warning_code == "APPLICATION_DEFINED_NUMBER_FORMAT"
                else f"Unsupported numberingChange NFC value {nfc}."
            )
            append_warning(
                warnings,
                warning_code,
                message,
                part=part,
                block_id=block_id,
            )
            continue
        if format_name not in NumberFormatRenderer._NFC_FORMATS.values():
            format_name = mapped_format
        prefix = first_prefix if match is definitions[0][0] else ""
        template = f"{prefix}%{level_number}{separator}"
        significant_length += len(f"%{level_number}{separator}".replace("%%", "%"))
        level_index = max(0, level_number - 1)
        levels[level_index] = NumberingLevel(
            numbering_level=level_index,
            number_format=format_name,
            level_text=template,
            suffix="nothing",
        )

    if significant_length > 31:
        append_warning(
            warnings,
            "INVALID_NUMBERING_CHANGE",
            "The numberingChange original value exceeds Word's 31-character limit.",
            part=part,
            block_id=block_id,
        )
        return {}
    return levels


__all__ = ["parse_numbering_change"]
