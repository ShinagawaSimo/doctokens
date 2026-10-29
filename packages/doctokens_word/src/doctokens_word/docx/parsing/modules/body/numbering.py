"""Numbering."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ....model import NumberingLabel, ParseOptions, ParseWarning, StyleRecord, append_warning
from ....model.content import PropertyChange
from ....ooxml.namespaces import attr, first_child
from ....ooxml.numbering import NumberingState, parse_numbering_change
from ....ooxml.property_changes import selected_properties
from ....ooxml.styles import StyleMap


def _paragraph_style_id(paragraph: ET.Element, view: str) -> str | None:
    """Read the paragraph style ID."""
    paragraph_properties = selected_properties(first_child(paragraph, "w", "pPr"), view)
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
        self.last_change: PropertyChange | None = None

    def parse(
        self, paragraph: ET.Element, style_id: str | None, part: str, block_id: str, inherited: StyleRecord
    ) -> NumberingLabel | None:
        """Read the paragraph numbering and advance the numbering counter."""
        self.last_change = None
        paragraph_properties = selected_properties(first_child(paragraph, "w", "pPr"), str(self.options.revision_mode))
        numbering_properties = first_child(paragraph_properties, "w", "numPr")
        style_numbering = (
            (inherited.numbering_num_id, inherited.numbering_level or 0) if inherited.numbering_num_id is not None else None
        )
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
        numbering_change = first_child(numbering_properties, "w", "numberingChange")
        if self.options.revision_mode in {"original", "review"}:
            original = attr(numbering_change, "w", "original") if numbering_change is not None else None
            previous_levels = parse_numbering_change(original, self.warnings, part=part, block_id=block_id)
            if not previous_levels:
                previous_levels = None
        result = self.numbering_state.advance(
            num_id,
            level,
            part=part,
            block_id=block_id,
            level_overrides=previous_levels if self.options.revision_mode == "original" else None,
        )
        if result is not None and previous_levels and self.options.revision_mode == "review":
            before = self.numbering_state.current_label(num_id, level, previous_levels)
            if before != result["label"]:
                self.last_change = {
                    "scope": "numbering",
                    "before": before,
                    "after": result["label"],
                    "author": attr(numbering_change, "w", "author") or "",
                    "date": attr(numbering_change, "w", "date") or "",
                }
        return result

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
