"""Serialize PPTX inline reading semantics without mutating runs."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.output.xml import append, text

from ..model.presentation import Run


def append_runs(parent: ET.Element, runs: list[Run], fallback: str, density: str) -> None:
    if not runs:
        text(parent, fallback)
        return
    previous: tuple[object, ...] | None = None
    leaf = parent
    for run in runs:
        if kind := run.get("unparsed"):
            append(parent, "unsupported", type=kind)
            previous = None
            continue
        equation = run.get("equation")
        value = run.get("text", "")
        if not value and not equation:
            continue
        formatting = (run.get("format") or {}) if density == "semantic" else {}
        signature = (
            formatting.get("color") or None,
            formatting.get("highlight") or None,
            bool(formatting.get("strike")),
            bool(formatting.get("superscript")),
            bool(formatting.get("subscript")),
            bool(formatting.get("underline")),
            bool(formatting.get("italic")),
            bool(formatting.get("bold")),
            run.get("link") or None,
        )
        if not equation and signature == previous:
            text(leaf, value)
            continue
        node = parent
        if density == "semantic":
            if formatting.get("color"):
                node = append(node, "color", value=formatting["color"])
            if formatting.get("highlight"):
                node = append(node, "mark", value=formatting["highlight"])
            if formatting.get("strike"):
                node = append(node, "s")
            if formatting.get("superscript"):
                node = append(node, "sup")
            elif formatting.get("subscript"):
                node = append(node, "sub")
            if formatting.get("underline"):
                node = append(node, "u")
            if formatting.get("italic"):
                node = append(node, "i")
            if formatting.get("bold"):
                node = append(node, "b")
        if run.get("link"):
            node = append(node, "a", href=run["link"])
        if equation:
            append(node, "equation", str(equation), notation="latex")
            previous = None
        else:
            text(node, value)
            leaf, previous = node, signature
