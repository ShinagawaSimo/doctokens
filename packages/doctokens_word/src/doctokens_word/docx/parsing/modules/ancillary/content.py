"""Ancillary container text, preserving paragraph/cell boundaries for search."""

from __future__ import annotations

from collections.abc import Callable
from xml.etree import ElementTree as ET

from ....model import AncillaryContent, RawHint, Run
from ....model.blocks import AncillarySearchParagraph
from ....ooxml.content_controls import parse_content_control
from ....ooxml.namespaces import (
    _TAG_W_PARAGRAPH,
    _TAG_W_SDT_CONTENT,
    _TAG_W_SMART_TAG,
    _TAG_W_STRUCTURED_DOCUMENT_TAG,
    _TAG_W_TABLE,
    attr,
    child_elements,
    first_child,
)
from ..body.inline import InlineParser


def has_objects(runs: list[Run]) -> bool:
    return any("objects" in run or "ruby" in run for run in runs)


class AncillaryContentParser:
    def __init__(self, inline: InlineParser, next_block_id: Callable[[str], str]) -> None:
        self.inline = inline
        self.next_block_id = next_block_id
        self._tables = 0

    def read(self, node: ET.Element, part: str) -> AncillaryContent:
        text_parts: list[str] = []
        runs: list[Run] = []
        hints: list[RawHint] = []
        units: list[AncillarySearchParagraph] = []
        for child in node:
            if self.inline.revisions.marker(child, part):
                continue
            if child.tag == _TAG_W_PARAGRAPH:
                style = first_child(first_child(child, "w", "pPr"), "w", "pStyle")
                style_id = attr(style, "w", "val") if style is not None else None
                p_runs, p_hints = self.inline.paragraph_runs(child, part, self.next_block_id(part), style_id)
                value = "".join(run["text"] for run in p_runs)
                if not (value.strip() or has_objects(p_runs)):
                    continue
                if runs:
                    runs.append({"text": "\n"})
                runs.extend(p_runs)
                text_parts.append(value)
                hints.extend(p_hints)
                units.append({"text": value})
            elif child.tag in {_TAG_W_TABLE, _TAG_W_STRUCTURED_DOCUMENT_TAG, _TAG_W_SDT_CONTENT, _TAG_W_SMART_TAG}:
                nested = self._table(child, part) if child.tag == _TAG_W_TABLE else self.read(child, part)
                if child.tag == _TAG_W_STRUCTURED_DOCUMENT_TAG:
                    control = parse_content_control(child)
                    for run in nested["runs"]:
                        run.setdefault("contentControls", []).append(control)
                    hints.append(dict(control))
                if nested["text"].strip() or has_objects(nested["runs"]):
                    if runs:
                        runs.append({"text": "\n"})
                    runs.extend(nested["runs"])
                    text_parts.append(nested["text"])
                    hints.extend(nested["rawHints"])
                    units.extend(nested.get("searchUnits", []))
        return {"text": "\n".join(text_parts), "runs": runs, "rawHints": hints, "searchUnits": units}

    def _table(self, node: ET.Element, part: str) -> AncillaryContent:
        self._tables += 1
        table = self._tables
        text_rows: list[str] = []
        runs: list[Run] = []
        hints: list[RawHint] = []
        units: list[AncillarySearchParagraph] = []
        for row, tr in enumerate(child_elements(node, "w", "tr"), 1):
            cells = [self.read(tc, part) for tc in child_elements(tr, "w", "tc")]
            for column, cell in enumerate(cells, 1):
                units.extend({"table": table, "row": row, "column": column, **unit} for unit in cell.get("searchUnits", []))
            visible = [cell for cell in cells if cell["text"].strip() or has_objects(cell["runs"])]
            if not visible:
                continue
            if runs:
                runs.append({"text": "\n"})
            row_texts: list[str] = []
            for index, cell in enumerate(visible):
                if index:
                    runs.append({"text": " | "})
                runs.extend(cell["runs"])
                row_texts.append(cell["text"].strip())
                hints.extend(cell["rawHints"])
            text_rows.append(" | ".join(value for value in row_texts if value))
        return {"text": "\n".join(text_rows), "runs": runs, "rawHints": hints, "searchUnits": units}
