"""Numbering."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ....core.constants import (
    attr,
    first_child,
)
from ....core.models import (
    NumberingLabel,
    ParseOptions,
    ParseWarning,
    append_warning,
)
from ....ooxml.numbering import NumberingState, parse_numbering_change
from ....ooxml.styles import StyleMap


def _paragraph_style_id(paragraph: ET.Element) -> str | None:
    """Read the paragraph style ID."""
    paragraph_properties = first_child(paragraph, "w", "pPr")
    pstyle = first_child(paragraph_properties, "w", "pStyle")
    return attr(pstyle, "w", "val") if pstyle is not None else None


class ParagraphNumbering:
    """Resolve paragraph numbering overrides and advance document counters."""

    def __init__(
        self, styles: StyleMap, numbering_state: NumberingState, options: ParseOptions, warnings: list[ParseWarning]
    ) -> None:
        self.styles = styles
        self.numbering_state = numbering_state
        self.options = options
        self.warnings = warnings

    def parse(self, paragraph: ET.Element, style_id: str | None, part: str, block_id: str) -> NumberingLabel | None:
        """Read the paragraph numbering and advance the numbering counter."""
        paragraph_properties = first_child(paragraph, "w", "pPr")
        numbering_properties = first_child(paragraph_properties, "w", "numPr")
        style_numbering = self.styles.resolve_numbering(style_id)
        direct_num_id, direct_numbering_level = self._num_pr_values(numbering_properties)

        if direct_num_id == "0":
            # numId=0 means numbering is off in Word; it also doesn't fall back to the style's numbering.
            return None
        num_id = direct_num_id or (style_numbering[0] if style_numbering else None)
        if num_id is None:
            return None
        level = direct_numbering_level
        if level is None:
            if style_numbering:
                level = self.numbering_state.numbering.level_for_style(style_numbering[0], style_id or "")
                if level is None:
                    level = style_numbering[1]
            else:
                level = 0

        previous_levels = None
        if self.options.revision_mode == "original":
            numbering_change = first_child(paragraph_properties, "w", "numberingChange")
            original = attr(numbering_change, "w", "original") if numbering_change is not None else None
            previous_levels = parse_numbering_change(original, self.warnings, part=part, block_id=block_id)
            if not previous_levels:
                previous_levels = None
        return self.numbering_state.advance(
            num_id,
            level,
            part=part,
            block_id=block_id,
            level_overrides=previous_levels,
        )

    def _num_pr_values(self, numbering_properties: ET.Element | None) -> tuple[str | None, int | None]:
        """Read numId and ilvl from w:numPr."""
        if numbering_properties is None:
            return (None, None)
        num_id_node = first_child(numbering_properties, "w", "numId")
        ilvl_node = first_child(numbering_properties, "w", "ilvl")
        num_id = attr(num_id_node, "w", "val") if num_id_node is not None else None
        level_str = attr(ilvl_node, "w", "val") if ilvl_node is not None else None
        if level_str is None:
            return (num_id, None)
        try:
            return (num_id, int(level_str))
        except ValueError:
            # An invalid level must not abort parsing; treat it as level 0 and record a warning.
            append_warning(
                self.warnings,
                "INVALID_PARAGRAPH_NUMBERING_LEVEL",
                f"Invalid paragraph numbering level: {level_str!r}",
                part="word/document.xml",
            )
            return (num_id, 0)
