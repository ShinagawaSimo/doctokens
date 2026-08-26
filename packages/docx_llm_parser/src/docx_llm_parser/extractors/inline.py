"""Parse paragraph-level WordprocessingML nodes and inline wrappers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from ..core.constants import (
    _TAG_W_DELETION_TEXT,
    attr,
    first_child,
    local_name,
)
from ..core.models import (
    AssetLookup,
    InlineObject,
    ObjectLookup,
    ParseOptions,
    ParseWarning,
    RawHint,
    Run,
    append_warning,
)
from ..core.relationships import RelationshipIndex
from ..ooxml.content_controls import parse_content_control
from ..ooxml.styles import StyleMap
from .inline_objects import equation_object, parse_embedded_object
from .run_parser import RunParser

PageBreakCallback = Callable[[], None]
NavigationMarkerCallback = Callable[[str, str], None]


@dataclass
class _FieldContext:
    """One complex Word field while its result runs are being read."""

    instruction_parts: list[str] = field(default_factory=list)
    result_start: int | None = None


class InlineParser:
    """Traverse paragraph children and delegate individual run parsing."""

    def __init__(
        self,
        styles: StyleMap,
        options: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: AssetLookup,
        object_lookup: ObjectLookup | None = None,
        on_page_break: PageBreakCallback | None = None,
        on_bookmark: NavigationMarkerCallback | None = None,
        on_comment_anchor: NavigationMarkerCallback | None = None,
    ) -> None:
        self.styles = styles
        self.options = options
        self.warnings = warnings
        self.relationships = relationships
        self.asset_lookup = asset_lookup
        self.object_lookup = object_lookup or {}
        self.on_page_break = on_page_break
        self.on_bookmark = on_bookmark
        self.on_comment_anchor = on_comment_anchor
        self._field_stack: list[_FieldContext] = []
        self._run_parser = RunParser(self)

    def field_context_type(self) -> _FieldContext:
        return _FieldContext()

    def paragraph_runs(
        self,
        p: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
    ) -> tuple[list[Run], list[RawHint]]:
        """Parse paragraph children into runs and raw diagnostic hints."""
        runs: list[Run] = []
        raw_hints: list[RawHint] = []
        self._field_stack = []
        try:
            for child in p:
                self._extract_inline_runs(child, part, block_id, paragraph_style_id, raw_hints, runs)
        finally:
            self._field_stack = []
        return runs, raw_hints

    def _extract_inline_runs(
        self,
        node: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> None:
        """Dispatch paragraph-level wrappers while preserving document order."""
        lname = local_name(node.tag)
        if lname == "pPr":
            return
        if lname == "r":
            self._append_run(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname == "hyperlink":
            self._append_hyperlink_runs(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname in {"ins", "moveTo"}:
            self._append_inserted_runs(
                node,
                part,
                block_id,
                paragraph_style_id,
                raw_hints,
                runs,
                label="move destination" if lname == "moveTo" else "insertion",
            )
            return
        if lname in {"del", "moveFrom"}:
            self._append_deleted_run(node, part, block_id, runs, label="move source" if lname == "moveFrom" else "deletion")
            return
        if lname in {"sdt", "sdtContent", "smartTag"}:
            self._append_control_runs(node, lname, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname in {"oMath", "oMathPara"}:
            self._append_object_run(equation_object(node), raw_hints, runs)
            return
        if lname == "bookmarkStart":
            name = attr(node, "w", "name")
            if name and not name.startswith("_"):
                self._mark_bookmark(name, block_id)
            return
        if lname in {"bookmarkEnd", "proofErr", "permStart", "permEnd"}:
            return
        if lname == "fldSimple":
            self._append_simple_field_runs(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname == "object":
            self._append_object_run(parse_embedded_object(node), raw_hints, runs)
            return
        if lname.startswith("commentRange"):
            comment_id = attr(node, "w", "id")
            if comment_id:
                self._mark_comment_anchor(comment_id, block_id)
            return
        self._warn("UNSUPPORTED_PARAGRAPH_CHILD", f"Encountered unsupported paragraph child: {lname}", part, block_id)

    def _append_control_runs(
        self,
        node: ET.Element,
        lname: str,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> None:
        if lname != "sdt":
            self._append_child_runs(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        control = parse_content_control(node)
        raw_hints.append(dict(control))
        start = len(runs)
        content = first_child(node, "w", "sdtContent")
        if content is not None:
            self._append_child_runs(content, part, block_id, paragraph_style_id, raw_hints, runs)
        for child_run in runs[start:]:
            child_run.setdefault("contentControls", []).append(control)

    def _append_run(
        self,
        run_element: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> None:
        parsed_runs = self._run_parser.parse(run_element, part, block_id, paragraph_style_id, raw_hints, runs)
        runs.extend(
            run
            for run in parsed_runs
            if run["text"] or "objects" in run or "pageBreak" in run or self.options.preserve_empty_paragraphs
        )

    def _append_child_runs(
        self,
        container: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> None:
        for child in container:
            self._extract_inline_runs(child, part, block_id, paragraph_style_id, raw_hints, runs)

    def _append_hyperlink_runs(
        self,
        hyperlink: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> None:
        link = self._run_parser.hyperlink_info(hyperlink, part)
        raw_hints.append({"type": "hyperlink", **link})
        start = len(runs)
        self._append_child_runs(hyperlink, part, block_id, paragraph_style_id, raw_hints, runs)
        for linked_run in runs[start:]:
            linked_run["link"] = link

    def _append_inserted_runs(
        self,
        insertion: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
        *,
        label: str = "insertion",
    ) -> None:
        self._warn(
            "REVISION_INSERTION_INCLUDED",
            f"Encountered {label} revision; parser includes inserted text in final/review mode.",
            part,
            block_id,
        )
        if self.options.revision_mode not in {"final", "review"}:
            return
        start = len(runs)
        self._append_child_runs(insertion, part, block_id, paragraph_style_id, raw_hints, runs)
        for inserted_run in runs[start:]:
            if self.options.revision_mode == "review":
                inserted_run["revision"] = "inserted"
                self._run_parser.add_revision_metadata(inserted_run, insertion)

    def _append_deleted_run(self, deletion: ET.Element, part: str, block_id: str, runs: list[Run], *, label: str) -> None:
        self._warn(
            "REVISION_DELETION_SKIPPED",
            f"Encountered {label} revision; deletion handling depends on revision_mode.",
            part,
            block_id,
        )
        if self.options.revision_mode not in {"original", "review"}:
            return
        deleted_text = "".join((item.text or "") for item in deletion.iter(_TAG_W_DELETION_TEXT))
        if not deleted_text:
            return
        deleted_run: Run = {"text": deleted_text}
        if self.options.revision_mode == "review":
            deleted_run["revision"] = "deleted"
            self._run_parser.add_revision_metadata(deleted_run, deletion)
        runs.append(deleted_run)

    def _append_simple_field_runs(
        self,
        field_node: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> None:
        start = len(runs)
        self._append_child_runs(field_node, part, block_id, paragraph_style_id, raw_hints, runs)
        self._run_parser.apply_field_instruction(attr(field_node, "w", "instr") or "", runs[start:])

    @staticmethod
    def _append_object_run(obj: InlineObject, raw_hints: list[RawHint], runs: list[Run]) -> None:
        runs.append({"text": "", "objects": [obj]})
        raw_hints.append(obj)

    def _mark_page_break(self) -> None:
        if self.on_page_break is not None:
            self.on_page_break()

    def _mark_bookmark(self, name: str, block_id: str) -> None:
        if self.on_bookmark is not None:
            self.on_bookmark(name, block_id)

    def _mark_comment_anchor(self, comment_id: str, block_id: str) -> None:
        if self.on_comment_anchor is not None:
            self.on_comment_anchor(comment_id, block_id)

    def _warn(self, code: str, message: str, part: str | None = None, block_id: str | None = None) -> None:
        append_warning(self.warnings, code, message, part=part, block_id=block_id)
