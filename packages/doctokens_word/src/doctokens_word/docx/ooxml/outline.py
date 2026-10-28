"""Read explicit paragraph outline levels without heading heuristics."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ..model import ParseWarning, append_warning
from .namespaces import attr, first_child


def parse_outline_level(
    properties: ET.Element | None,
    warnings: list[ParseWarning],
    *,
    part: str,
    block_id: str | None = None,
) -> int | None:
    """Keep 9 as an explicit cancellation; ignore invalid values with a warning."""
    node = first_child(properties, "w", "outlineLvl")
    if node is None:
        return None
    value = attr(node, "w", "val")
    try:
        level = int(value) if value is not None else -1
        if 0 <= level <= 9:
            return level
    except ValueError:
        pass
    append_warning(warnings, "INVALID_OUTLINE_LEVEL", f"Invalid outline level {value!r}", part=part, block_id=block_id)
    return None
