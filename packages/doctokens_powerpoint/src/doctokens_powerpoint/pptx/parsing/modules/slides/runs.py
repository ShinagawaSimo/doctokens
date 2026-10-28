"""Runs."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning
from doctokens_core.ooxml.equations.converter import convert_math

from ....model.presentation import Paragraph, ParagraphStyle, Run, RunFormat
from ....ooxml.colors import is_default_text_color, resolve_color_element
from ....ooxml.math import TEXT_MATH
from ....ooxml.namespaces import attr, first_child, local_name
from .lists import integer as _parse_int
from .lists import list_metadata, list_prefix
from .text import HyperlinkLookup


def tx_body_text(
    tx_body: ET.Element | None, part: str, warnings: list[ParseWarning], *, source_paragraphs: list[str] | None = None
) -> str | None:
    """Join a txBody's paragraphs into one text block (paragraphs by \\n)."""
    if tx_body is None:
        return None
    paragraphs: list[str] = []
    counters: dict[tuple[str, int], int] = {}
    for child in tx_body:
        # bodyPr/lstStyle are formatting infrastructure: skipped silently.
        if local_name(child.tag) == "p":
            text = paragraph_text(child, part, warnings, counters, source_paragraphs=source_paragraphs)
            if text:
                paragraphs.append(text)
    if not paragraphs:
        return None
    return "\n".join(paragraphs)


def paragraph_text(
    p: ET.Element,
    part: str,
    warnings: list[ParseWarning],
    counters: dict[tuple[str, int], int] | None = None,
    *,
    source_paragraphs: list[str] | None = None,
) -> str:
    """Flatten a paragraph's runs/breaks/tabs/fields into plain text."""
    runs = paragraph_runs(p, part, warnings, {}, {}, {})
    metadata = list_metadata(p, {})
    if not any(run.get("text", "").strip() for run in runs):
        return ""
    if source_paragraphs is not None:
        source_paragraphs.append("".join(run.get("text", "") for run in runs))
    pr = first_child(p, "a", "pPr")
    prefix = list_prefix(
        metadata, _parse_int(pr.get("lvl") if pr is not None else None, 0), counters if counters is not None else {}
    )
    return prefix + "".join(run.get("text", "") for run in runs)


def shape_runs(
    tx_body: ET.Element | None,
    part: str,
    warnings: list[ParseWarning],
    theme: dict[str, str],
    color_map: dict[str, str],
    links: HyperlinkLookup,
    inherited_styles: dict[int, ParagraphStyle] | None = None,
    paragraphs_out: list[Paragraph] | None = None,
    include_formatting: bool = True,
) -> list[Run]:
    """Run-level IR for a txBody: paragraphs joined by synthetic newline runs."""
    if tx_body is None:
        return []
    runs: list[Run] = []
    counters: dict[tuple[str, int], int] = {}
    for child in tx_body:
        if local_name(child.tag) != "p":
            continue
        p_pr = first_child(child, "a", "pPr")
        level = _parse_int(p_pr.get("lvl") if p_pr is not None else None, 0)
        style = (inherited_styles or {}).get(level, (inherited_styles or {}).get(0, {}))
        base_format = cast(RunFormat, dict(style.get("runFormat", {}))) if include_formatting else {}
        if include_formatting and p_pr is not None:
            def_r_pr = first_child(p_pr, "a", "defRPr")
            if def_r_pr is not None:
                base_format.update(_format_properties(def_r_pr, theme, color_map, warnings, part))
        paragraph = paragraph_runs(
            child,
            part,
            warnings,
            theme,
            color_map,
            links,
            base_format,
            include_formatting=include_formatting,
        )
        metadata = list_metadata(child, style)
        if metadata and not any(run.get("text", "").strip() for run in paragraph):
            continue
        prefix = list_prefix(metadata, level, counters)
        if prefix:
            paragraph.insert(0, {"text": prefix})
        if paragraph:
            if paragraphs_out is not None:
                metadata["text"] = "".join(run.get("text", "") for run in paragraph)
                metadata["level"] = level
                metadata["runs"] = paragraph
                paragraphs_out.append(metadata)
            if runs:
                runs.append({"text": "\n"})
            runs.extend(paragraph)
    return runs


def paragraph_runs(
    p: ET.Element,
    part: str,
    warnings: list[ParseWarning],
    theme: dict[str, str],
    color_map: dict[str, str],
    links: HyperlinkLookup,
    base_format: RunFormat | None = None,
    *,
    include_formatting: bool = True,
) -> list[Run]:
    """Per-run extraction with rPr formats, hyperlinks, breaks, tabs, fields."""
    runs: list[Run] = []
    pending = ""
    for child in p:
        name = local_name(child.tag)
        if name in {"r", "fld"}:
            if pending:
                runs.append({"text": pending})
                pending = ""
            text = _run_text(child)
            run: Run = {}
            if text:
                run["text"] = text
            run_format = cast(RunFormat, dict(base_format or {})) if include_formatting else {}
            if include_formatting:
                run_format.update(_run_format(child, theme, color_map, warnings, part))
            if run_format:
                run["format"] = run_format
            link = _run_link(child, links, part)
            if link:
                run["link"] = link
            if run:
                runs.append(run)
        elif name == "br":
            pending += "\n"
        elif name == "tab":
            pending += "\t"
        elif name in {"pPr", "endParaRPr"}:
            continue
        elif name in {"oMath", "oMathPara"} or child.tag == TEXT_MATH:
            if pending:
                runs.append({"text": pending})
                pending = ""
            nodes = child if child.tag == TEXT_MATH else (child,)
            for node in nodes:
                if local_name(node.tag) not in {"oMath", "oMathPara"}:
                    continue
                latex = convert_math(node, warn=lambda code, message: warnings.append(ParseWarning(code, message, part))).text
                if latex:
                    runs.append({"text": latex, "equation": latex})
        else:
            warnings.append(
                ParseWarning(
                    code="UNSUPPORTED_PARAGRAPH_CHILD",
                    message=f"Unsupported paragraph child: {name}",
                    locator=part,
                )
            )
    if pending:
        runs.append({"text": pending})
    return runs


def _run_text(r: ET.Element) -> str:
    t = first_child(r, "a", "t")
    return t.text if t is not None and t.text else ""


def _run_format(
    r: ET.Element,
    theme: dict[str, str],
    color_map: dict[str, str],
    warnings: list[ParseWarning],
    part: str,
) -> RunFormat:
    r_pr = first_child(r, "a", "rPr")
    if r_pr is None:
        return {}
    return _format_properties(r_pr, theme, color_map, warnings, part)


def _format_properties(
    r_pr: ET.Element,
    theme: dict[str, str],
    color_map: dict[str, str],
    warnings: list[ParseWarning],
    part: str,
) -> RunFormat:
    fmt: RunFormat = {}
    if r_pr.get("b") is not None:
        fmt["bold"] = _drawingml_bool(r_pr.get("b"))
    elif first_child(r_pr, "a", "b") is not None:
        fmt["bold"] = True
    if r_pr.get("i") is not None:
        fmt["italic"] = _drawingml_bool(r_pr.get("i"))
    elif first_child(r_pr, "a", "i") is not None:
        fmt["italic"] = True
    underline_value = r_pr.get("u")
    underline = first_child(r_pr, "a", "u")
    if underline_value is not None:
        fmt["underline"] = underline_value not in {"none", "0", "false", "off"}
    elif underline is not None:
        fmt["underline"] = underline.get("val", "") not in {"none", "0", "false", "off"}
    solid_fill = first_child(r_pr, "a", "solidFill")
    if solid_fill is not None:
        for color_element in solid_fill:
            color = resolve_color_element(
                color_element,
                theme,
                color_map=color_map,
                warnings=warnings,
                locator=part,
            )
            if color and not is_default_text_color(color):
                fmt["color"] = color
                break
    return fmt


def _drawingml_bool(value: str | None) -> bool:
    return value is not None and value.lower() not in {"0", "false", "off", "no"}


def _run_link(r: ET.Element, links: HyperlinkLookup, part: str) -> str | None:
    r_pr = first_child(r, "a", "rPr")
    if r_pr is None:
        return None
    hlink = first_child(r_pr, "a", "hlinkClick")
    if hlink is None:
        return None
    rid = attr(hlink, "r", "id")
    if rid is not None:
        return links.get((part, rid))
    return hlink.get("action")
