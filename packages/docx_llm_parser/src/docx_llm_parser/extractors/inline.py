"""Parse WordprocessingML paragraph inline content."""

from __future__ import annotations

from collections.abc import Callable
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
from ..core.models import (
    AssetLookup,
    InlineObject,
    LinkInfo,
    ObjectLookup,
    ParseOptions,
    ParseWarning,
    RawHint,
    Run,
    append_warning,
)
from ..core.relationships import RelationshipIndex
from ..ooxml.formatting import merge_run_formats, parse_run_format, visible_run_format
from ..ooxml.styles import StyleMap
from .inline_objects import (
    drawing_objects,
    equation_object,
    parse_embedded_object,
    pict_objects,
)

PageBreakCallback = Callable[[], None]


class InlineParser:
    """Parse text, links, formatting, and lightweight objects in a paragraph into a unified run stream."""

    def __init__(
        self,
        styles: StyleMap,
        options: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: AssetLookup,
        object_lookup: ObjectLookup | None = None,
        on_page_break: PageBreakCallback | None = None,
    ) -> None:
        self.styles = styles
        self.options = options
        self.warnings = warnings
        self.relationships = relationships
        self.asset_lookup = asset_lookup
        self.object_lookup = object_lookup or {}
        self.on_page_break = on_page_break

    def paragraph_runs(
        self,
        p: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
    ) -> tuple[list[Run], list[RawHint]]:
        """Parse the runs in a paragraph and return raw hints for debugging."""
        runs: list[Run] = []
        raw_hints: list[RawHint] = []
        for child in p:
            self._extract_inline_runs(child, part, block_id, paragraph_style_id, raw_hints, runs)
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
        """Recursively process paragraph inline nodes, preserving the structure Word explicitly provides."""
        # Optimization: use local_name to avoid split memory allocation (called thousands of times per second on the hot path).
        lname = local_name(node.tag)
        if lname == "pPr":
            # Paragraph properties are handled by the outer block parser.
            return
        if lname == "r":
            # A run is Word's common carrier for text and inline objects.
            self._append_run(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname == "hyperlink":
            # Hyperlink display text reuses the normal inline parsing; the link target is attached as a lightweight attribute.
            self._append_hyperlink_runs(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname == "ins":
            # Insertion revisions are visible text in final/review views.
            self._append_inserted_runs(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname == "del":
            # Deletion revisions are only emitted in original/review views.
            self._append_deleted_run(node, part, block_id, runs)
            return
        if lname in {"sdt", "sdtContent", "smartTag"}:
            # Content controls and smart tags are wrapper layers; keep reading their visible content.
            self._append_child_runs(node, part, block_id, paragraph_style_id, raw_hints, runs)
            return
        if lname in {"oMath", "oMathPara"}:
            # Paragraph-level OMML equations enter the final XML as lightweight objects.
            self._append_object_run(equation_object(node), raw_hints, runs)
            return
        if lname in {"bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd"}:
            # These markers don't contribute readable text.
            return
        if lname == "object":
            self._append_object_run(parse_embedded_object(node), raw_hints, runs)
            return
        if lname.startswith("commentRange"):
            # A comment range itself carries no content; commentReference and comments.xml handle the association.
            self._warn(
                "COMMENT_ANCHOR_UNSUPPORTED",
                "Encountered comment range marker; parser records commentReference when present.",
                part=part,
                block_id=block_id,
            )
            return
        self._warn(
            "UNSUPPORTED_PARAGRAPH_CHILD",
            f"Encountered unsupported paragraph child: {lname}",
            part=part,
            block_id=block_id,
        )

    def _append_run(
        self,
        run_element: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> None:
        run = self._parse_run(run_element, part, block_id, paragraph_style_id, raw_hints)
        if run["text"] or "objects" in run or self.options.preserve_empty_paragraphs:
            runs.append(run)

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
        link = self._hyperlink_info(hyperlink, part)
        raw_hints.append({"type": "hyperlink", **link})
        linked_runs: list[Run] = []
        self._append_child_runs(hyperlink, part, block_id, paragraph_style_id, raw_hints, linked_runs)
        for linked_run in linked_runs:
            linked_run["link"] = link
            runs.append(linked_run)

    def _append_inserted_runs(
        self,
        insertion: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> None:
        self._warn(
            "REVISION_INSERTION_INCLUDED",
            "Encountered insertion revision; parser includes inserted text in final/review mode.",
            part=part,
            block_id=block_id,
        )
        if self.options.revision_mode not in {"final", "review"}:
            return

        inserted_runs: list[Run] = []
        self._append_child_runs(insertion, part, block_id, paragraph_style_id, raw_hints, inserted_runs)
        for inserted_run in inserted_runs:
            if self.options.revision_mode == "review":
                inserted_run["revision"] = "inserted"
            runs.append(inserted_run)

    def _append_deleted_run(
        self,
        deletion: ET.Element,
        part: str,
        block_id: str,
        runs: list[Run],
    ) -> None:
        self._warn(
            "REVISION_DELETION_SKIPPED",
            "Encountered deletion revision; deletion handling depends on revision_mode.",
            part=part,
            block_id=block_id,
        )
        if self.options.revision_mode not in {"original", "review"}:
            return

        deleted_text = "".join((item.text or "") for item in deletion.iter(_TAG_W_DELETION_TEXT))
        if not deleted_text:
            return

        deleted_run: Run = {"text": deleted_text}
        if self.options.revision_mode == "review":
            deleted_run["revision"] = "deleted"
        runs.append(deleted_run)

    @staticmethod
    def _append_object_run(obj: InlineObject, raw_hints: list[RawHint], runs: list[Run]) -> None:
        runs.append({"text": "", "objects": [obj]})
        raw_hints.append(obj)

    def _parse_run(
        self,
        run_element: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
    ) -> Run:
        """Parse a run's visible text, necessary formatting, and inline objects.
        Optimization: iterate all children of the run once, dispatching by tag name.
        Previously this required first_child(run, 'rPr') plus a child loop (two scans);
        now it's merged into a single iteration."""
        text_parts: list[str] = []
        run_properties: ET.Element | None = None
        parsed_run: Run = {"text": ""}

        # Single pass: collect rPr and process text/object children at the same time.
        for child in run_element:
            # Optimization: compare against precomputed tag names to avoid repeated qualified_name() calls.
            child_tag = child.tag
            if child_tag == _TAG_W_RUN_PROPERTIES:
                run_properties = child
            else:
                self._handle_run_child(
                    child,
                    part,
                    block_id,
                    raw_hints,
                    parsed_run,
                    text_parts,
                )

        # After iterating over the children, resolve rPr (already found in the loop above).
        if run_properties is not None:
            rstyle = first_child(run_properties, "w", "rStyle")
            run_style_id = attr(rstyle, "w", "val") if rstyle is not None else None
            if run_style_id is not None:
                parsed_run["styleId"] = run_style_id
            run_format = merge_run_formats(
                self.styles.resolve_run_format(paragraph_style_id),
                self.styles.resolve_run_format(run_style_id),
                parse_run_format(run_properties),
            )
            visible_format = visible_run_format(run_format)
            if visible_format:
                parsed_run["format"] = visible_format

        parsed_run["text"] = "".join(text_parts)
        return parsed_run

    def _handle_run_child(
        self,
        child: ET.Element,
        part: str,
        block_id: str,
        raw_hints: list[RawHint],
        parsed_run: Run,
        text_parts: list[str],
    ) -> None:
        """Dispatch one run child into text, inline objects or warnings."""
        child_tag = child.tag
        if child_tag == _TAG_W_TEXT:
            text_parts.append(child.text or "")
        elif child_tag == _TAG_W_TAB:
            text_parts.append("\t")
        elif child_tag in (_TAG_W_BREAK, _TAG_W_CARRIAGE_RETURN):
            text_parts.append("\n")
            if attr(child, "w", "type") == "page":
                raw_hints.append({"type": "manualPageBreak"})
                self._mark_page_break()
        elif child_tag == _TAG_W_LAST_RENDERED_PAGE_BREAK:
            raw_hints.append({"type": "lastRenderedPageBreak"})
            self._mark_page_break()
        elif child_tag == _TAG_W_DRAWING:
            objects = drawing_objects(child, part, self.asset_lookup, self.object_lookup)
            parsed_run.setdefault("objects", []).extend(objects)
            raw_hints.extend({"type": "drawing", **obj} for obj in objects)
        elif child_tag == _TAG_W_PICTURE:
            objects = pict_objects(child)
            parsed_run.setdefault("objects", []).extend(objects)
            raw_hints.extend({"type": "pict", **obj} for obj in objects)
        elif child_tag in (_TAG_M_OMATH, _TAG_M_OMATH_PARA):
            obj = equation_object(child)
            parsed_run.setdefault("objects", []).append(obj)
            raw_hints.append(obj)
        elif child_tag in (_TAG_W_FLD_CHAR, _TAG_W_INSTR_TEXT):
            lname = local_name(child_tag)
            field_hint: RawHint = {"type": "field", "node": lname}
            if lname == "instrText" and child.text:
                field_hint["instruction"] = child.text
                parsed_run.setdefault("objects", []).append({"type": "fieldInstruction", "instruction": child.text})
            raw_hints.append(field_hint)
        elif child_tag in (_TAG_W_FOOTNOTE_REF, _TAG_W_ENDNOTE_REF, _TAG_W_ANNOTATION_REF):
            return
        elif child_tag in (_TAG_W_FOOTNOTE_REFERENCE, _TAG_W_ENDNOTE_REFERENCE):
            note_id = attr(child, "w", "id")
            lname = local_name(child_tag)
            ref_type = "footnote" if lname == "footnoteReference" else "endnote"
            obj = {"type": f"{ref_type}Ref", "id": note_id}
            parsed_run.setdefault("objects", []).append(obj)
            raw_hints.append(obj)
        elif child_tag == _TAG_W_COMMENT_REFERENCE:
            obj = {"type": "commentRef", "id": attr(child, "w", "id")}
            parsed_run.setdefault("objects", []).append(obj)
            raw_hints.append(obj)
        elif child_tag == _TAG_W_DELETION_TEXT:
            # The final view doesn't read deleted text by default.
            self._warn(
                "DELETED_TEXT_SKIPPED",
                "Encountered deleted text in run; parser skips deleted text in final mode.",
                part=part,
                block_id=block_id,
            )
        elif child_tag == _TAG_W_OBJECT:
            obj = parse_embedded_object(child)
            parsed_run.setdefault("objects", []).append(obj)
            raw_hints.append(obj)
        elif child_tag == _TAG_W_RUN_STYLE:
            # rStyle is extracted uniformly via first_child in the rPr section below; just skip it here.
            return
        else:
            self._warn(
                "UNSUPPORTED_RUN_CHILD",
                f"Encountered unsupported run child: {local_name(child_tag)}",
                part=part,
                block_id=block_id,
            )

    def _hyperlink_info(self, node: ET.Element, part: str) -> LinkInfo:
        """Parse the hyperlink target; the final XML only uses href/anchor."""
        rel_id = attr(node, "r", "id")
        anchor = attr(node, "w", "anchor")
        info: LinkInfo = {}
        if rel_id:
            rel = self.relationships.get(part, rel_id)
            if rel is None:
                # A dangling r:id must not abort the whole parse; keep the display text.
                self._warn(
                    "HYPERLINK_TARGET_MISSING",
                    f"Hyperlink r:id={rel_id!r} has no matching relationship; keeping display text only.",
                    part=part,
                )
            else:
                info["href"] = rel.resolved_target or rel.target
        if anchor:
            info["anchor"] = anchor
        return info

    def _mark_page_break(self) -> None:
        """Notify the body parser that the page hint must advance after the current block."""
        if self.on_page_break is not None:
            self.on_page_break()

    def _warn(
        self,
        code: str,
        message: str,
        part: str | None = None,
        block_id: str | None = None,
    ) -> None:
        """Append a parse warning."""
        append_warning(self.warnings, code, message, part=part, block_id=block_id)
