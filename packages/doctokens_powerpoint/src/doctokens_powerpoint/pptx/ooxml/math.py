"""Resolve nested paragraph math alternatives with their original namespaces."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from .namespaces import NS
from .unsupported import unparsed_element

TEXT_MATH = "{http://schemas.microsoft.com/office/drawing/2010/main}m"
_M = f"{{{NS['m']}}}"
_MATH = frozenset((TEXT_MATH, _M + "oMath", _M + "oMathPara"))
_ALTERNATE = f"{{{NS['mc']}}}AlternateContent"
_CHOICE = f"{{{NS['mc']}}}Choice"
_FALLBACK = f"{{{NS['mc']}}}Fallback"
_PARAGRAPH = f"{{{NS['a']}}}p"
_INLINE = _MATH | {f"{{{NS['a']}}}{name}" for name in ("r", "br", "tab", "fld")}
_SUPPORTED = frozenset((NS["a"], NS["m"], "http://schemas.microsoft.com/office/drawing/2010/main"))


def normalize_math(root: ET.Element, supported_choices: set[ET.Element], warnings: list[ParseWarning], part: str) -> None:
    """Select paragraph math only after outer shape alternatives are resolved."""
    for paragraph in root.iter(_PARAGRAPH):
        children: list[ET.Element] = []
        for child in paragraph:
            if child.tag != _ALTERNATE or not _contains_math(child):
                children.append(child)
                continue
            selected = _select(child, supported_choices, math_context=False)
            if selected is None:
                warnings.append(
                    ParseWarning("MATH_ALTERNATE_CONTENT_UNSUPPORTED", "Math has no readable Choice or Fallback", part)
                )
                children.append(unparsed_element("equation"))
            else:
                children.extend(selected)
        paragraph[:] = children


def _contains_math(node: ET.Element) -> bool:
    return any(child.tag in _MATH for child in node.iter())


def _select(alternate: ET.Element, supported: set[ET.Element], *, math_context: bool) -> list[ET.Element] | None:
    # Rejected branches produce no diagnostics or content. Only the final
    # selected representation participates in the paragraph's ordinary parser.
    for choice in alternate:
        if choice.tag == _CHOICE and choice in supported:
            result = _expand(choice, supported, math_context=math_context)
            if result is not None:
                return result
    fallback = next((node for node in alternate if node.tag == _FALLBACK), None)
    if fallback is not None:
        return _expand(fallback, supported, math_context=math_context)
    return None


def _expand(container: ET.Element, supported: set[ET.Element], *, math_context: bool) -> list[ET.Element] | None:
    result: list[ET.Element] = []
    for node in container:
        if node.tag == _ALTERNATE:
            selected = _select(node, supported, math_context=math_context)
            if selected is None:
                return None
            result.extend(selected)
            continue
        if node.tag not in _INLINE and not (math_context and node.tag.startswith(_M)):
            return None
        # Math-zone content can itself contain compatibility choices. Preserve
        # other native children (including Word revision wrappers) as objects.
        if (node.tag in _MATH or node.tag.startswith(_M)) and not _normalize_math_children(node, supported):
            return None
        result.append(node)
    return result


def _normalize_math_children(node: ET.Element, supported: set[ET.Element]) -> bool:
    children: list[ET.Element] = []
    for child in node:
        if child.tag == _ALTERNATE:
            selected = _select(child, supported, math_context=True)
            if selected is None:
                return False
            children.extend(selected)
        else:
            if not _normalize_math_children(child, supported):
                return False
            children.append(child)
    node[:] = children
    return True
