"""Ruby base reading text and its saved phonetic annotation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ....model import RawHint, Run, RunFormat
from ....ooxml.characters import word_character
from ....ooxml.namespaces import first_child, local_name

if TYPE_CHECKING:
    from .inline import InlineParser


def ruby_run(
    owner: InlineParser, node: ET.Element, part: str, block_id: str, style: str | None, hints: list[RawHint], inherited: RunFormat
) -> Run:
    if owner.ruby_depth >= 32:
        owner._warn("RUBY_NESTING_LIMIT", "Ruby nesting exceeds 32 annotations.", part, block_id)
        return {"text": ""}
    base = first_child(node, "w", "rubyBase")
    if base is None:
        owner._warn("RUBY_BASE_MISSING", "Ruby has no base text container.", part, block_id)
        return {"text": ""}
    base_runs: list[Run] = []
    # A field in ruby content has local run offsets; an enclosing field applies
    # to the resulting ruby run rather than consuming its private run list.
    outer_fields = owner._field_stack
    outer_format = owner.ruby_format
    owner._field_stack = []
    owner.ruby_format = inherited
    owner.ruby_depth += 1
    try:
        owner._append_child_runs(base, part, block_id, style, hints, base_runs)
    finally:
        owner._field_stack = outer_fields
        owner.ruby_format = outer_format
        owner.ruby_depth -= 1
    annotation = first_child(node, "w", "rt")
    guide = _guide_text(owner, annotation, part, block_id) if annotation is not None else ""
    text = "".join(run["text"] for run in base_runs)
    return {"text": text, "ruby": {"annotation": guide, "baseRuns": base_runs}}


def _guide_text(owner: InlineParser, node: ET.Element, part: str, block_id: str) -> str:
    pieces: list[str] = []
    stack = [(node, False)]
    while stack:
        child, deleted = stack.pop()
        name = local_name(child.tag)
        if name in {"del", "moveFrom"}:
            if owner.options.revision_mode == "final":
                continue
            deleted = True
        if name in {"ins", "moveTo"} and owner.options.revision_mode == "original":
            continue
        if name == "t" or (name == "delText" and (deleted or owner.revisions.deleted_depth)):
            pieces.append(child.text or "")
        elif name.endswith("Pr") or name in {"instrText", "delInstrText"}:
            continue
        elif name == "tab":
            pieces.append("\t")
        elif name in {"br", "cr"}:
            pieces.append("\n")
        elif (character := word_character(child, lambda code, message: owner._warn(code, message, part, block_id))) is not None:
            pieces.append(character)
        else:
            stack.extend((item, deleted) for item in reversed(child))
    return "".join(pieces)
