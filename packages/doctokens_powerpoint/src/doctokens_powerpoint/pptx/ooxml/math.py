"""Resolve nested paragraph math alternatives with their original namespaces."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from .namespaces import NS
from .package import PackageReader

TEXT_MATH = "{http://schemas.microsoft.com/office/drawing/2010/main}m"
_M = f"{{{NS['m']}}}"
_MATH = frozenset((TEXT_MATH, _M + "oMath", _M + "oMathPara"))
_ALTERNATE = f"{{{NS['mc']}}}AlternateContent"
_CHOICE = f"{{{NS['mc']}}}Choice"
_FALLBACK = f"{{{NS['mc']}}}Fallback"
_PARAGRAPH = f"{{{NS['a']}}}p"
_INLINE = _MATH | {f"{{{NS['a']}}}{name}" for name in ("r", "br", "tab", "fld")}
_SUPPORTED = frozenset((NS["a"], NS["m"], "http://schemas.microsoft.com/office/drawing/2010/main"))


def read_math_part(package: PackageReader, part: str, warnings: list[ParseWarning]) -> ET.Element:
    """Record real namespace bindings, then select only paragraph math content."""
    bindings: dict[str, str] = {}
    pending: list[tuple[str, str]] = []
    stack: list[list[tuple[str, str | None]]] = []
    supported_choices: set[ET.Element] = set()
    root: ET.Element | None = None
    with package.open_entry(part) as stream:
        for event, item in ET.iterparse(stream, events=("start-ns", "start", "end")):
            if event == "start-ns":
                pending.append(cast(tuple[str, str], item))
                continue
            element = cast(ET.Element, item)
            if event == "start":
                previous = [(prefix, bindings.get(prefix)) for prefix, _uri in pending]
                bindings.update(pending)
                pending.clear()
                stack.append(previous)
                if element.tag == _CHOICE:
                    prefixes = element.get("Requires", "").split()
                    if prefixes and all(bindings.get(prefix) in _SUPPORTED for prefix in prefixes):
                        supported_choices.add(element)
                continue
            for prefix, uri in stack.pop():
                if uri is None:
                    bindings.pop(prefix, None)
                else:
                    bindings[prefix] = uri
            root = element
    if root is None:
        raise ET.ParseError("empty XML part")
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
            else:
                children.extend(selected)
        paragraph[:] = children
    return root


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
