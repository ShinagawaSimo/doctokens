"""Parse one WordprocessingML run and preserve inline page boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ....model import InlineObject, LinkInfo, RawHint, Run, RunFormat
from ....ooxml.characters import word_character
from ....ooxml.fields import apply_field_instruction
from ....ooxml.formatting import merge_run_formats, parse_run_format, visible_run_format
from ....ooxml.namespaces import (
    _TAG_M_OMATH,
    _TAG_M_OMATH_PARA,
    _TAG_W_ANNOTATION_REF,
    _TAG_W_BREAK,
    _TAG_W_CARRIAGE_RETURN,
    _TAG_W_COMMENT_REFERENCE,
    _TAG_W_DELETED_INSTR_TEXT,
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
from .objects import drawing_objects, parse_embedded_object
from .ruby import ruby_run
from .vml import pict_objects

if TYPE_CHECKING:
    from .inline import InlineParser


class RunParser:
    """Own the low-level run parser while delegating document policy to ``InlineParser``."""

    def __init__(self, owner: InlineParser) -> None:
        self.owner = owner

    def parse(
        self,
        run_element: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> None:
        """Append run fragments in source order, including object and field boundaries."""
        run_properties = first_child(run_element, "w", "rPr")
        run_style_id = None
        if run_properties is not None:
            rstyle = first_child(run_properties, "w", "rStyle")
            run_style_id = attr(rstyle, "w", "val") if rstyle is not None else None
        visible_format = {}
        run_format: RunFormat = {}
        if self.owner.include_character_formatting:
            run_format = merge_run_formats(
                self.owner.styles.resolve_run_format(paragraph_style_id),
                self.owner.ruby_format,
                self.owner.styles.resolve_run_format(run_style_id),
                parse_run_format(run_properties),
            )
            visible_format = visible_run_format(run_format)
        for child in run_element:
            if child.tag == _TAG_W_RUN_PROPERTIES:
                continue
            if local_name(child.tag) == "ruby":
                parsed_run = ruby_run(self.owner, child, part, block_id, paragraph_style_id, raw_hints, run_format)
            else:
                text_parts: list[str] = []
                objects: list[InlineObject] = []
                self._handle_child(child, part, block_id, raw_hints, text_parts, objects, runs)
                parsed_run = {"text": "".join(text_parts)}
                if objects:
                    parsed_run["objects"] = objects
            if run_style_id is not None and self.owner.include_character_formatting:
                parsed_run["styleId"] = run_style_id
            if visible_format and "ruby" not in parsed_run:
                parsed_run["format"] = visible_format
            if (
                parsed_run["text"]
                or parsed_run.get("objects")
                or (parsed_run.get("ruby") and parsed_run["ruby"]["baseRuns"])
                or self.owner.options.preserve_empty_paragraphs
            ):
                runs.append(parsed_run)

    def _handle_child(
        self,
        child: ET.Element,
        part: str,
        block_id: str,
        raw_hints: list[RawHint],
        text_parts: list[str],
        objects: list[InlineObject],
        runs: list[Run],
    ) -> None:
        child_tag = child.tag
        if child_tag == _TAG_W_TEXT:
            text_parts.append(child.text or "")
        elif (
            character := word_character(child, lambda code, message: self.owner._warn(code, message, part, block_id))
        ) is not None:
            text_parts.append(character)
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
            if self.owner.include_raw_hints:
                raw_hints.append({"type": "lastRenderedPageBreak"})
            self.owner._mark_page_break()
            runs.append({"text": "", "pageBreak": True})
        elif child_tag == _TAG_W_DRAWING:
            drawing = drawing_objects(child, part, self.owner.asset_lookup, self.owner.object_lookup, self.owner.textbox_reader)
            objects.extend(drawing)
            if self.owner.include_raw_hints:
                raw_hints.extend({"type": "drawing", **obj} for obj in drawing)
        elif child_tag == _TAG_W_PICTURE:
            pict = pict_objects(child, part, self.owner.asset_lookup, self.owner.textbox_reader)
            objects.extend(pict)
            if self.owner.include_raw_hints:
                raw_hints.extend({"type": "pict", **obj} for obj in pict)
        elif child_tag in (_TAG_M_OMATH, _TAG_M_OMATH_PARA):
            obj: InlineObject = self.owner.read_equation(child, part, block_id)
            if obj.get("text"):
                objects.append(obj)
                if self.owner.include_raw_hints:
                    raw_hints.append(obj)
        elif child_tag == _TAG_W_FLD_CHAR:
            self.handle_field_character(child, raw_hints, runs, part, block_id)
        elif child_tag in {_TAG_W_INSTR_TEXT, _TAG_W_DELETED_INSTR_TEXT}:
            if child_tag == _TAG_W_DELETED_INSTR_TEXT and not self.owner.revisions.deleted_depth:
                return
            instruction = child.text or ""
            if self.owner._field_stack:
                self.owner._field_stack[-1].instruction_parts.append(instruction)
            field_hint: RawHint = {"type": "field", "node": "instrText"}
            if instruction:
                field_hint["instruction"] = instruction
            if self.owner.include_raw_hints:
                raw_hints.append(field_hint)
        elif child_tag in (_TAG_W_FOOTNOTE_REF, _TAG_W_ENDNOTE_REF, _TAG_W_ANNOTATION_REF):
            return
        elif child_tag in (_TAG_W_FOOTNOTE_REFERENCE, _TAG_W_ENDNOTE_REFERENCE):
            note_id = attr(child, "w", "id")
            ref_type = "footnote" if local_name(child_tag) == "footnoteReference" else "endnote"
            obj = {"type": f"{ref_type}Ref", "id": note_id}
            objects.append(obj)
            if self.owner.include_raw_hints:
                raw_hints.append(obj)
        elif child_tag == _TAG_W_COMMENT_REFERENCE:
            obj = {"type": "commentRef", "id": attr(child, "w", "id")}
            objects.append(obj)
            if self.owner.include_raw_hints:
                raw_hints.append(obj)
            comment_id = obj.get("id")
            if isinstance(comment_id, str):
                self.owner._mark_comment_anchor(comment_id, block_id)
        elif child_tag == _TAG_W_DELETION_TEXT:
            if self.owner.revisions.deleted_depth:
                text_parts.append(child.text or "")
            else:
                self.owner._warn("DELETED_TEXT_SKIPPED", "Deleted text outside a selected deletion was skipped.", part, block_id)
        elif child_tag == _TAG_W_OBJECT:
            obj = parse_embedded_object(child)
            objects.append(obj)
            if self.owner.include_raw_hints:
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

    def handle_field_character(
        self, field_char: ET.Element, raw_hints: list[RawHint], runs: list[Run], part: str, block_id: str
    ) -> None:
        """Track complex-field boundaries without emitting field-code text."""
        field_type = attr(field_char, "w", "fldCharType") or ""
        if self.owner.include_raw_hints:
            raw_hints.append({"type": "field", "node": "fldChar", "state": field_type})
        if field_type == "begin":
            self.owner._field_stack.append(self.owner.field_context_type())
        elif field_type == "separate" and self.owner._field_stack:
            self.owner._field_stack[-1].result_start = len(runs)
        elif field_type == "end" and self.owner._field_stack:
            context = self.owner._field_stack.pop()
            if context.result_start is not None:
                apply_field_instruction(
                    "".join(context.instruction_parts),
                    runs[context.result_start :],
                    lambda code, message: self.owner._warn(code, message, part, block_id),
                )

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
