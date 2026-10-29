"""Flatten ancillary stories while preserving selected paragraph and table relationships."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from xml.etree import ElementTree as ET

from ....model import AncillaryContent, RawHint, Run
from ....model.blocks import AncillarySearchParagraph
from ....ooxml.namespaces import first_child, local_name
from ....ooxml.property_changes import apply_property_review, revision_record, selected_properties, structural_revision
from ....ooxml.table_styles import TableStyleResolver
from ....ooxml.wrapped_content import content_children
from ..body.inline import InlineParser
from ..body.numbering import _paragraph_style_id
from ..body.paragraph_groups import ParagraphPart, joins_next
from ..body.table_geometry import table_rows


def has_objects(runs: list[Run]) -> bool:
    return any("objects" in run or "ruby" in run or "paragraphMark" in run for run in runs)


class AncillaryContentParser:
    def __init__(self, inline: InlineParser, next_block_id: Callable[[str], str]) -> None:
        self.inline = inline
        self.next_block_id = next_block_id
        self._tables = 0

    def read(self, node: ET.Element, part: str) -> AncillaryContent:
        runs: list[Run] = []
        hints: list[RawHint] = []
        units: list[AncillarySearchParagraph] = []
        texts: list[str] = []
        pending: list[ParagraphPart] = []
        view = str(self.inline.options.revision_mode)

        def append(content: AncillaryContent) -> None:
            if not (content["text"].strip() or has_objects(content["runs"])):
                return
            if runs:
                runs.append({"text": "\n"})
            runs.extend(content["runs"])
            texts.append(content["text"])
            hints.extend(content["rawHints"])
            units.extend(content.get("searchUnits", []))

        def flush() -> None:
            if not pending:
                return
            paragraph = next(item[0] for item in reversed(pending) if local_name(item[0].tag) == "p")
            style = self.inline.styles.style_id(_paragraph_style_id(paragraph, view), "paragraph")
            p_runs, p_hints = self.inline.paragraph_runs(paragraph, part, self.next_block_id(part), style, pending)
            properties = first_child(paragraph, "w", "pPr")
            for run in p_runs:
                apply_property_review(run, properties, "paragraph", view)
            mark = structural_revision(first_child(properties, "w", "rPr"))
            if view == "review" and mark is not None:
                p_runs.append({"text": "", "paragraphMark": revision_record(mark)})
            value = "".join(run["text"] for run in p_runs)
            append({"text": value, "runs": p_runs, "rawHints": p_hints, "searchUnits": [{"text": value}]})
            pending.clear()

        for child, controls in content_children(node):
            name = local_name(child.tag)
            if name == "p":
                pending.append((child, controls))
                if not joins_next(child, view):
                    flush()
            elif name.startswith(("moveFromRange", "moveToRange")):
                if pending:
                    pending.append((child, controls))
                else:
                    self.inline.revisions.marker(child, part)
            elif name == "tbl":
                flush()
                content = self._table(child, part)
                for run in content["runs"]:
                    run.setdefault("contentControls", []).extend(controls)
                append(content)
        flush()
        return {"text": "\n".join(texts), "runs": runs, "rawHints": hints, "searchUnits": units}

    def _table(self, node: ET.Element, part: str) -> AncillaryContent:
        self._tables += 1
        table = self._tables
        view = str(self.inline.options.revision_mode)
        sources = table_rows(node, view, self.inline.warnings, part, self.inline.options.max_table_columns)
        columns = max((row.width for row in sources), default=0)
        resolver = TableStyleResolver(
            self.inline.styles, selected_properties(first_child(node, "w", "tblPr"), view), len(sources), columns
        )
        runs: list[Run] = []
        hints: list[RawHint] = []
        units: list[AncillarySearchParagraph] = []
        text_rows: list[str] = []
        for row, source in enumerate(sources):
            segments: list[list[Run]] = [[{"text": ""}] for _ in range(source.before)]
            row_texts: list[str] = [""] * source.before
            row_pr = first_child(source.node, "w", "trPr")
            row_markup: Run = {"text": ""}
            apply_property_review(row_markup, row_pr, "row", view)
            exceptions = first_child(source.node, "w", "tblPrEx")
            apply_property_review(row_markup, exceptions, "row-table", view)
            row_resolver = resolver.row_exception(selected_properties(exceptions, view))
            for cell in source.cells:
                cell_pr = first_child(cell.node, "w", "tcPr")
                revisions = [structural_revision(row_pr), structural_revision(cell_pr)]
                deleted = any(
                    revision is not None and local_name(revision.tag) in {"del", "cellDel", "moveFrom"} for revision in revisions
                )
                outer = self.inline.table_style
                outer_resolver = self.inline.table_style_for_paragraph
                self.inline.table_style = row_resolver.cell(row, cell.column, cell.span, source.properties, cell.properties)
                self.inline.table_style_for_paragraph = partial(
                    row_resolver.cell, row, cell.column, cell.span, source.properties, cell.properties
                )
                self.inline.revisions.deleted_depth += int(deleted)
                try:
                    content = self.read(cell.node, part)
                finally:
                    self.inline.table_style = outer
                    self.inline.table_style_for_paragraph = outer_resolver
                    self.inline.revisions.deleted_depth -= int(deleted)
                cell_markup: Run = {"text": ""}
                apply_property_review(cell_markup, cell_pr, "cell", view)
                for run in content["runs"]:
                    markers = [*row_markup.get("revisions", []), *cell_markup.get("revisions", []), *run.get("revisions", [])]
                    if markers:
                        run["revisions"] = markers
                    changes = [
                        *row_markup.get("propertyChanges", []),
                        *cell_markup.get("propertyChanges", []),
                        *run.get("propertyChanges", []),
                    ]
                    if changes:
                        run["propertyChanges"] = changes
                    run.setdefault("contentControls", []).extend((*source.controls, *cell.controls))
                segments.append(content["runs"])
                segments.extend([{"text": ""}] for _ in range(cell.span - 1))
                row_texts.append(content["text"])
                row_texts.extend("" for _ in range(cell.span - 1))
                hints.extend(content["rawHints"])
                units.extend(
                    {**unit, "table": table, "row": row + 1, "column": cell.column + 1} for unit in content.get("searchUnits", [])
                )
            row_texts.extend("" for _ in range(source.after))
            if runs:
                runs.append({"text": "\n"})
            segments.extend([{"text": ""}] for _ in range(source.after))
            for index, segment in enumerate(segments):
                if index:
                    runs.append({"text": " | "})
                runs.extend(segment)
            text_rows.append(" | ".join(row_texts))
        return {"text": "\n".join(text_rows), "runs": runs, "rawHints": hints, "searchUnits": units}
