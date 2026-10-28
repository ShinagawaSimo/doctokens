"""Selected inline revision content and named move ranges for one story."""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ....model import RawHint, Run
from ....model.content import Revision
from ....ooxml.namespaces import attr, local_name

if TYPE_CHECKING:
    from .inline import InlineParser


class InlineRevisions:
    def __init__(self, owner: InlineParser) -> None:
        self.owner = owner
        self.deleted_depth = 0
        self.ranges: dict[tuple[str, str, str], str] = {}

    def marker(self, node: ET.Element, part: str) -> bool:
        name = local_name(node.tag)
        for prefix in ("moveFrom", "moveTo"):
            key = (part, prefix, attr(node, "w", "id") or "")
            if name == prefix + "RangeStart":
                self.ranges[key] = attr(node, "w", "name") or ""
                return True
            if name == prefix + "RangeEnd":
                self.ranges.pop(key, None)
                return True
        return False

    def append(
        self, node: ET.Element, part: str, block_id: str, style: str | None, hints: list[RawHint], runs: list[Run]
    ) -> None:
        owner = self.owner
        name = local_name(node.tag)
        deleted = name in {"del", "moveFrom"}
        owner._warn(
            "REVISION_DELETION_SKIPPED" if deleted else "REVISION_INSERTION_INCLUDED",
            f"Encountered {name} revision; visibility follows revision_mode.",
            part,
            block_id,
        )
        if owner.options.revision_mode == ("final" if deleted else "original"):
            return
        move_name = next(
            (value for (story_part, kind, _id), value in self.ranges.items() if story_part == part and kind == name), ""
        )
        start = len(runs)
        self.deleted_depth += int(deleted)
        try:
            owner._append_child_runs(node, part, block_id, style, hints, runs)
        finally:
            self.deleted_depth -= int(deleted)
        if owner.options.revision_mode != "review":
            return
        revision: Revision = {
            "kind": "deleted" if deleted else "inserted",
            "author": attr(node, "w", "author") or "",
            "date": attr(node, "w", "date") or "",
            "moveName": move_name,
        }
        if name in {"moveFrom", "moveTo"}:
            revision["kind"] = "moved-from" if deleted else "moved-to"
        for run in runs[start:]:
            run.setdefault("revisions", []).insert(0, revision)
