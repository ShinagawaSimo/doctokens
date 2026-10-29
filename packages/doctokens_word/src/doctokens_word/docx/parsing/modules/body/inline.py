"""Parse paragraph-level WordprocessingML nodes and inline wrappers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.relationships import RelationshipIndex
from doctokens_core.ooxml.equations.results import RevisionView

from ....model import (
    AssetLookup,
    ContentControl,
    InlineObject,
    ObjectLookup,
    ParseOptions,
    ParseWarning,
    RawHint,
    Run,
    RunFormat,
    StyleRecord,
    append_warning,
)
from ....ooxml.content_controls import parse_content_control
from ....ooxml.fields import apply_field_instruction
from ....ooxml.namespaces import attr, first_child, local_name
from ....ooxml.property_changes import selected_properties
from ....ooxml.styles import StyleMap
from ...plan import DocxFeature, DocxParsePlan
from .equations import equation_object
from .objects import parse_embedded_object
from .paragraph_groups import ParagraphPart
from .revisions import InlineRevisions
from .runs import RunParser
from .textboxes import TextboxReader

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
        plan: DocxParsePlan | None = None,
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
        self.plan = plan or DocxParsePlan.session()
        self.include_raw_hints = self.plan.needs(DocxFeature.RAW_HINTS)
        self.include_character_formatting = self.plan.needs(DocxFeature.CHARACTER_FORMATTING)
        self.on_page_break = on_page_break
        self.on_bookmark = on_bookmark
        self.on_comment_anchor = on_comment_anchor
        self._field_stack: list[_FieldContext] = []
        self._run_parser = RunParser(self)
        self.revisions = InlineRevisions(self)
        self.ruby_format: RunFormat = {}
        self.ruby_depth = 0
        self.table_style = StyleRecord(style_id="")
        self.table_style_for_paragraph: Callable[[ET.Element | None], StyleRecord] | None = None
        self.textbox_reader: TextboxReader | None = None

    def field_context_type(self) -> _FieldContext:
        return _FieldContext()

    def paragraph_runs(
        self,
        p: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        parts: list[ParagraphPart] | None = None,
        common_controls: tuple[ContentControl, ...] = (),
    ) -> tuple[list[Run], list[RawHint]]:
        """Parse paragraph children into runs and raw diagnostic hints."""
        runs: list[Run] = []
        raw_hints: list[RawHint] = []
        self._field_stack = []
        outer_table_style = self.table_style
        if self.table_style_for_paragraph is not None:
            self.table_style = self.table_style_for_paragraph(
                selected_properties(first_child(p, "w", "pPr"), str(self.options.revision_mode))
            )
        try:
            for source, controls in parts or [(p, ())]:
                start = len(runs)
                if local_name(source.tag) == "p":
                    for child in source:
                        self._extract_inline_runs(child, part, block_id, paragraph_style_id, raw_hints, runs)
                else:
                    self._extract_inline_runs(source, part, block_id, paragraph_style_id, raw_hints, runs)
                if controls != common_controls:
                    for run in runs[start:]:
                        run.setdefault("contentControls", []).extend(controls)
        finally:
            self._field_stack = []
            self.table_style = outer_table_style
        ordinal = 0
        for run in runs:
            for item in run.get("objects", []):
                if item["type"] == "textbox" and item.get("placement") == "anchor":
                    ordinal += 1
                    scope = "" if part == "word/document.xml" else f"{part}-"
                    item["id"] = f"tb-{scope}{block_id}-{ordinal}"
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
            self._run_parser.parse(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname == "hyperlink":
            self._append_hyperlink_runs(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname in {"ins", "del", "moveTo", "moveFrom"}:
            self.revisions.append(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if self.revisions.marker(node, part):
            return
        if lname in {"sdt", "sdtContent", "smartTag"}:
            self._append_control_runs(node, lname, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname in {"oMath", "oMathPara"}:
            self._append_object_run(self.read_equation(node, part, block_id), raw_hints, runs)
            return
        if lname == "bookmarkStart":
            name = attr(node, "w", "name")
            if name:
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
        if self.include_raw_hints:
            raw_hints.append(dict(control))
        start = len(runs)
        content = first_child(node, "w", "sdtContent")
        if content is not None:
            self._append_child_runs(content, part, block_id, paragraph_style_id, raw_hints, runs)
        for child_run in runs[start:]:
            child_run.setdefault("contentControls", []).append(control)

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
        if self.include_raw_hints:
            raw_hints.append({"type": "hyperlink", **link})
        start = len(runs)
        self._append_child_runs(hyperlink, part, block_id, paragraph_style_id, raw_hints, runs)
        for linked_run in runs[start:]:
            linked_run["link"] = link

    def read_equation(self, node: ET.Element, part: str, block_id: str) -> InlineObject:
        return equation_object(
            node,
            revision_mode=cast(RevisionView, self.options.revision_mode),
            warn=lambda code, message: self._warn(code, message, part, block_id),
        )

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
        apply_field_instruction(
            attr(field_node, "w", "instr") or "",
            runs[start:],
            lambda code, message: self._warn(code, message, part, block_id),
        )

    def _append_object_run(self, obj: InlineObject, raw_hints: list[RawHint], runs: list[Run]) -> None:
        if obj["type"] == "equation" and not obj.get("text"):
            return
        runs.append({"text": "", "objects": [obj]})
        if self.include_raw_hints:
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
