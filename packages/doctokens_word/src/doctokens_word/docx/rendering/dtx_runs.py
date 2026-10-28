"""DTX reading marks for a run: revisions, references, ruby, and emphasis."""

from __future__ import annotations

from collections.abc import Callable
from xml.etree import ElementTree as ET

from doctokens_core.output.xml import append

from ..model import Run, RunFormat
from .common.text import filter_format
from .dtx_content import _append_text_with_breaks


def revision_parent(parent: ET.Element, run: Run, density: str) -> ET.Element:
    if density == "semantic":
        for revision in run.get("revisions", []):
            parent = append(
                parent,
                {"inserted": "ins", "deleted": "del", "moved-from": "move-from", "moved-to": "move-to"}[revision["kind"]],
                author=revision["author"] or None,
                date=revision["date"] or None,
                name=revision["moveName"] or None,
            )
    return parent


def append_run_text(parent: ET.Element, run: Run, density: str, append_base: Callable[[ET.Element, list[Run]], None]) -> None:
    if not run["text"] and not run.get("ruby"):
        return
    node = parent
    field = run.get("field")
    if density == "semantic" and field and field.get("kind") == "citation" and field.get("key"):
        node = append(node, "cite", key=field["key"])
    link = run.get("link")
    if link:
        node = append(node, "a", href=link.get("href") or None, anchor=link.get("anchor") or None)
    if density == "semantic":
        node = _format_parent(node, filter_format(run))
    ruby = run.get("ruby")
    if ruby:
        if density == "semantic" and ruby["annotation"]:
            node = append(node, "ruby", annotation=ruby["annotation"])
        append_base(node, ruby["baseRuns"])
    else:
        _append_text_with_breaks(node, run["text"])


def _format_parent(parent: ET.Element, run_format: RunFormat) -> ET.Element:
    node = parent
    if run_format.get("bg") or run_format.get("highlight"):
        node = append(node, "mark", value=run_format.get("bg") or run_format.get("highlight"))
    if run_format.get("color"):
        node = append(node, "color", value=run_format["color"])
    for key, tag in (
        ("strike", "s"),
        ("underline", "u"),
        ("italic", "i"),
        ("bold", "b"),
        ("superscript", "sup"),
        ("subscript", "sub"),
        ("smallCaps", "small-caps"),
    ):
        if run_format.get(key):
            node = append(node, tag)
    return node
