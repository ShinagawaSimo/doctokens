"""Sections."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ....model import Block
from ....model.traversal import iter_blocks
from ....ooxml.namespaces import attr, first_child, local_name
from ....ooxml.property_changes import selected_properties


class BodySections:
    """Keep section boundaries and referenced headers/footers in document order."""

    def __init__(self) -> None:
        self._section_header_refs: list[tuple[str, str]] = []
        self._section_footer_refs: list[tuple[str, str]] = []
        self._section_index = 1
        self._section_break_pending = False
        self._start_types: dict[int, str] = {}

    def _collect_section_refs(self, sect_pr: ET.Element, view: str = "final") -> None:
        """Extract header/footer references from sectPr."""
        properties = selected_properties(sect_pr, view)
        self._start_types[self._section_index] = attr(first_child(properties, "w", "type"), "w", "val") or "nextPage"
        for child in properties if properties is not None else ():
            lname = local_name(child.tag)
            r_id = attr(child, "r", "id")
            if not r_id:
                continue
            ref_type = attr(child, "w", "type") or "default"
            if lname == "headerReference":
                self._section_header_refs.append((r_id, ref_type))
            elif lname == "footerReference":
                self._section_footer_refs.append((r_id, ref_type))

    def correct_continuous_pages(self, blocks: list[Block]) -> None:
        """Section type belongs to the section ending at its sectPr, not the following one."""
        offsets: dict[int, int] = {}
        offset = 0
        for section in range(1, self._section_index + 1):
            if section > 1 and self._start_types.get(section) == "continuous":
                offset += 1
            offsets[section] = offset
        for top in blocks:
            shift = offsets.get(top.get("section", 1), 0)
            if not shift:
                continue
            for block in iter_blocks([top]):
                block["page"] -= shift
                if "pageEnd" in block:
                    block["pageEnd"] -= shift
                if block["type"] != "table":
                    for segment in block.get("pageSegments", []):
                        value = segment.get("page")
                        if isinstance(value, int):
                            segment["page"] = value - shift

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
