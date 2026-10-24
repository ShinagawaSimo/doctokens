"""Sections."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ....core.constants import (
    attr,
    local_name,
)


class BodySections:
    """Keep section boundaries and referenced headers/footers in document order."""

    def __init__(self) -> None:
        self._section_header_refs: list[tuple[str, str]] = []
        self._section_footer_refs: list[tuple[str, str]] = []
        self._section_index = 1
        self._section_break_pending = False

    def _collect_section_refs(self, sect_pr: ET.Element) -> None:
        """Extract header/footer references from sectPr."""
        for child in sect_pr:
            lname = local_name(child.tag)
            r_id = attr(child, "r", "id")
            if not r_id:
                continue
            ref_type = attr(child, "w", "type") or "default"
            if lname == "headerReference":
                self._section_header_refs.append((r_id, ref_type))
            elif lname == "footerReference":
                self._section_footer_refs.append((r_id, ref_type))

    def _begin_section(self) -> int:
        """Advance at the first content block after a Word section break."""
        if self._section_break_pending:
            self._section_index += 1
            self._section_break_pending = False
        return self._section_index

    @property
    def section_refs(self) -> dict[str, list[tuple[str, str]]]:
        """Return the collected section references so AncillaryParser can filter unused headers/footers."""
        return {
            "headers": list(self._section_header_refs),
            "footers": list(self._section_footer_refs),
        }
