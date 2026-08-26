"""Parse one WordprocessingML run and preserve inline page boundaries."""

from __future__ import annotations

import shlex
from collections.abc import Callable
from typing import Any
from xml.etree import ElementTree as ET

from ..core.constants import (
    _TAG_M_OMATH,
    _TAG_M_OMATH_PARA,
    _TAG_W_ANNOTATION_REF,
    _TAG_W_BREAK,
    _TAG_W_CARRIAGE_RETURN,
    _TAG_W_COMMENT_REFERENCE,
    _TAG_W_DELETION_TEXT,
    _TAG_W_DRAWING,
    _TAG_W_ENDNOTE_REF,
    _TAG_W_ENDNOTE_REFERENCE,
    _TAG_W_FLD_CHAR,
    _TAG_W_FOOTNOTE_REF,
    _TAG_W_FOOTNOTE_REFERENCE,
    _TAG_W_INSTR_TEXT,
    _TAG_W_LAST_RENDERED_PAGE_BREAK,
    _TAG_W_OBJECT,
    _TAG_W_PICTURE,
    _TAG_W_RUN_PROPERTIES,
    _TAG_W_RUN_STYLE,
    _TAG_W_TAB,
    _TAG_W_TEXT,
    attr,
    first_child,
    local_name,
)
from ..core.models import InlineObject, LinkInfo, RawHint, Run
from ..ooxml.formatting import merge_run_formats, parse_run_format, visible_run_format
from ..plan import DocxFeature
from .inline_objects import drawing_objects, equation_object, parse_embedded_object, pict_objects


class RunParser:
    """Own the low-level run parser while delegating document policy to ``InlineParser``."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def parse(
        self,
        run_element: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> list[Run]:
        """Parse a run and retain calculated page breaks at their inline positions."""
        text_segments: list[list[str]] = [[]]
        object_segments: list[list[InlineObject]] = [[]]
        run_properties: ET.Element | None = None

        def split_segment() -> None:
            text_segments.append([])
            object_segments.append([])

        for child in run_element:
            child_tag = child.tag
            if child_tag == _TAG_W_RUN_PROPERTIES:
                run_properties = child
            else:
                self._handle_child(
                    child,
                    part,
                    block_id,
                    raw_hints,
                    text_segments[-1],
                    object_segments[-1],
                    runs,
                    split_segment,
                )

        run_style_id = None
        if run_properties is not None:
            rstyle = first_child(run_properties, "w", "rStyle")
            run_style_id = attr(rstyle, "w", "val") if rstyle is not None else None
        visible_format = {}
        if self.owner.plan.needs(DocxFeature.CHARACTER_FORMATTING):
            run_format = merge_run_formats(
                self.owner.styles.resolve_run_format(paragraph_style_id),
                self.owner.styles.resolve_run_format(run_style_id),
                parse_run_format(run_properties),
            )
            visible_format = visible_run_format(run_format)
        parsed_runs: list[Run] = []
        for index, (text_parts, objects) in enumerate(zip(text_segments, object_segments, strict=True)):
            parsed_run: Run = {"text": "".join(text_parts)}
            if objects:
                parsed_run["objects"] = objects
            if run_style_id is not None and self.owner.plan.needs(DocxFeature.CHARACTER_FORMATTING):
                parsed_run["styleId"] = run_style_id
            if visible_format:
                parsed_run["format"] = visible_format
            parsed_runs.append(parsed_run)
            if index < len(text_segments) - 1:
                parsed_runs.append({"text": "", "pageBreak": True})
        return parsed_runs

    def _handle_child(
        self,
        child: ET.Element,
        part: str,
        block_id: str,
        raw_hints: list[RawHint],
        text_parts: list[str],
        objects: list[InlineObject],
        runs: list[Run],
        split_segment: Callable[[], None],
    ) -> None:
        child_tag = child.tag
        if child_tag == _TAG_W_TEXT:
            text_parts.append(child.text or "")
        elif child_tag == _TAG_W_TAB:
            text_parts.append("\t")
        elif child_tag in (_TAG_W_BREAK, _TAG_W_CARRIAGE_RETURN):
            text_parts.append("\n")
            if attr(child, "w", "type") == "page":
                # Pagination consumes this hint even when raw hints are not
                # retained on the final block.
                raw_hints.append({"type": "manualPageBreak"})
                self.owner._mark_page_break()
        elif child_tag == _TAG_W_LAST_RENDERED_PAGE_BREAK:
            if self.owner.plan.needs(DocxFeature.RAW_HINTS):
                raw_hints.append({"type": "lastRenderedPageBreak"})
            self.owner._mark_page_break()
            split_segment()
        elif child_tag == _TAG_W_DRAWING:
            drawing = drawing_objects(child, part, self.owner.asset_lookup, self.owner.object_lookup)
            objects.extend(drawing)
            if self.owner.plan.needs(DocxFeature.RAW_HINTS):
                raw_hints.extend({"type": "drawing", **obj} for obj in drawing)
        elif child_tag == _TAG_W_PICTURE:
            pict = pict_objects(child)
            objects.extend(pict)
            if self.owner.plan.needs(DocxFeature.RAW_HINTS):
                raw_hints.extend({"type": "pict", **obj} for obj in pict)
        elif child_tag in (_TAG_M_OMATH, _TAG_M_OMATH_PARA):
            obj = equation_object(child)
            objects.append(obj)
            if self.owner.plan.needs(DocxFeature.RAW_HINTS):
                raw_hints.append(obj)
        elif child_tag == _TAG_W_FLD_CHAR:
            self.handle_field_character(child, raw_hints, runs)
        elif child_tag == _TAG_W_INSTR_TEXT:
            instruction = child.text or ""
            if self.owner._field_stack:
                self.owner._field_stack[-1].instruction_parts.append(instruction)
            field_hint: RawHint = {"type": "field", "node": "instrText"}
            if instruction:
                field_hint["instruction"] = instruction
            if self.owner.plan.needs(DocxFeature.RAW_HINTS):
                raw_hints.append(field_hint)
        elif child_tag in (_TAG_W_FOOTNOTE_REF, _TAG_W_ENDNOTE_REF, _TAG_W_ANNOTATION_REF):
            return
        elif child_tag in (_TAG_W_FOOTNOTE_REFERENCE, _TAG_W_ENDNOTE_REFERENCE):
            note_id = attr(child, "w", "id")
            ref_type = "footnote" if local_name(child_tag) == "footnoteReference" else "endnote"
            obj = {"type": f"{ref_type}Ref", "id": note_id}
            objects.append(obj)
            if self.owner.plan.needs(DocxFeature.RAW_HINTS):
                raw_hints.append(obj)
        elif child_tag == _TAG_W_COMMENT_REFERENCE:
            obj = {"type": "commentRef", "id": attr(child, "w", "id")}
            objects.append(obj)
            if self.owner.plan.needs(DocxFeature.RAW_HINTS):
                raw_hints.append(obj)
            comment_id = obj.get("id")
            if isinstance(comment_id, str):
                self.owner._mark_comment_anchor(comment_id, block_id)
        elif child_tag == _TAG_W_DELETION_TEXT:
            self.owner._warn(
                "DELETED_TEXT_SKIPPED",
                "Encountered deleted text in run; parser skips deleted text in final mode.",
                part=part,
                block_id=block_id,
            )
        elif child_tag == _TAG_W_OBJECT:
            obj = parse_embedded_object(child)
            objects.append(obj)
            if self.owner.plan.needs(DocxFeature.RAW_HINTS):
                raw_hints.append(obj)
        elif child_tag == _TAG_W_RUN_STYLE:
            return
        else:
            self.owner._warn(
                "UNSUPPORTED_RUN_CHILD",
                f"Encountered unsupported run child: {local_name(child_tag)}",
                part=part,
                block_id=block_id,
            )

    def handle_field_character(self, field_char: ET.Element, raw_hints: list[RawHint], runs: list[Run]) -> None:
        """Track complex-field boundaries without emitting field-code text."""
        field_type = attr(field_char, "w", "fldCharType") or ""
        if self.owner.plan.needs(DocxFeature.RAW_HINTS):
            raw_hints.append({"type": "field", "node": "fldChar", "state": field_type})
        if field_type == "begin":
            self.owner._field_stack.append(self.owner.field_context_type())
        elif field_type == "separate" and self.owner._field_stack:
            self.owner._field_stack[-1].result_start = len(runs)
        elif field_type == "end" and self.owner._field_stack:
            context = self.owner._field_stack.pop()
            if context.result_start is not None:
                self.apply_field_instruction("".join(context.instruction_parts), runs[context.result_start :])

    @staticmethod
    def add_revision_metadata(run: Run, revision: ET.Element) -> None:
        author = attr(revision, "w", "author")
        date = attr(revision, "w", "date")
        if author:
            run["revisionAuthor"] = author
        if date:
            run["revisionDate"] = date

    @staticmethod
    def apply_field_instruction(instruction: str, result_runs: list[Run]) -> None:
        """Attach navigation and citation semantics to field result runs."""
        if not result_runs or not instruction.strip():
            return
        try:
            tokens = shlex.split(instruction)
        except ValueError:
            tokens = instruction.split()
        if not tokens:
            return
        kind, payload = tokens[0].upper(), tokens[1:]
        if kind in {"REF", "PAGEREF", "NOTEREF"}:
            target = next((token for token in payload if not token.startswith("\\")), "")
            if target:
                for run in result_runs:
                    run["link"] = {"anchor": target}
                    run["field"] = {"kind": "reference", "anchor": target}
        elif kind == "HYPERLINK":
            href = ""
            anchor = ""
            for index, token in enumerate(payload):
                if token.lower() == "\\l" and index + 1 < len(payload):
                    anchor = payload[index + 1]
                elif not token.startswith("\\") and not href:
                    href = token
            if href or anchor:
                link: LinkInfo = {}
                if href:
                    link["href"] = href
                if anchor:
                    link["anchor"] = anchor
                for run in result_runs:
                    run["link"] = link
                    run["field"] = {"kind": "reference", "anchor": anchor}
        elif kind == "CITATION":
            key = next((token for token in payload if not token.startswith("\\")), "")
            if key:
                for run in result_runs:
                    run["field"] = {"kind": "citation", "key": key}

    def hyperlink_info(self, node: ET.Element, part: str) -> LinkInfo:
        """Resolve a hyperlink target while preserving dangling-link degradation."""
        rel_id = attr(node, "r", "id")
        anchor = attr(node, "w", "anchor")
        info: LinkInfo = {}
        if rel_id:
            rel = self.owner.relationships.get(part, rel_id)
            if rel is None:
                self.owner._warn(
                    "HYPERLINK_TARGET_MISSING",
                    f"Hyperlink r:id={rel_id!r} has no matching relationship; keeping display text only.",
                    part=part,
                )
            else:
                info["href"] = rel.resolved_target or rel.target
        if anchor:
            info["anchor"] = anchor
        return info
