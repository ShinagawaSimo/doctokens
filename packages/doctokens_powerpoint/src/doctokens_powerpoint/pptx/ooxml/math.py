"""Select native DrawingML math alternatives while XML namespace scopes exist."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from .namespaces import NS
from .package import PackageReader

TEXT_MATH = "{http://schemas.microsoft.com/office/drawing/2010/main}m"
_MATH = frozenset((TEXT_MATH, f"{{{NS['m']}}}oMath", f"{{{NS['m']}}}oMathPara"))
_ALTERNATE = f"{{{NS['mc']}}}AlternateContent"
_CHOICE = f"{{{NS['mc']}}}Choice"
_FALLBACK = f"{{{NS['mc']}}}Fallback"
_PARAGRAPH = f"{{{NS['a']}}}p"
_INLINE = _MATH | {f"{{{NS['a']}}}{name}" for name in ("r", "br", "tab", "fld")}
_SUPPORTED = frozenset((NS["a"], NS["m"], "http://schemas.microsoft.com/office/drawing/2010/main"))


def read_math_part(package: PackageReader, part: str, warnings: list[ParseWarning]) -> ET.Element:
    """Read one slide/notes part, expanding only paragraph math alternatives.

    Requires prefixes are resolved in their original scopes, including aliases
    and local rebindings. Other AlternateContent, such as OLE previews or whole
    shapes, remains available to its own format-specific dispatcher.
    """
    bindings: dict[str, str] = {}
    pending: list[tuple[str, str]] = []
    stack: list[tuple[ET.Element, list[tuple[str, str | None]]]] = []
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
                stack.append((element, previous))
                if element.tag == _CHOICE:
                    prefixes = element.get("Requires", "").split()
                    if prefixes and all(bindings.get(prefix) in _SUPPORTED for prefix in prefixes):
                        supported_choices.add(element)
                continue
            if element.tag == _ALTERNATE and len(stack) > 1 and stack[-2][0].tag == _PARAGRAPH:
                _expand_math(element, stack[-2][0], supported_choices, part, warnings)
            _node, previous = stack.pop()
            for prefix, uri in previous:
                if uri is None:
                    bindings.pop(prefix, None)
                else:
                    bindings[prefix] = uri
            root = element
    if root is None:
        raise ET.ParseError("empty XML part")
    return root


def _expand_math(
    alternate: ET.Element,
    parent: ET.Element,
    supported_choices: set[ET.Element],
    part: str,
    warnings: list[ParseWarning],
) -> None:
    if not any(node.tag in _MATH for node in alternate.iter()):
        return
    selected = next(
        (
            choice
            for choice in alternate
            if choice.tag == _CHOICE and choice in supported_choices and all(node.tag in _INLINE for node in choice)
        ),
        None,
    )
    if selected is None:
        selected = next((node for node in alternate if node.tag == _FALLBACK), None)
    if selected is None:
        warnings.append(ParseWarning("MATH_ALTERNATE_CONTENT_UNSUPPORTED", "Math has no supported Choice or Fallback", part))
    index = list(parent).index(alternate)
    parent.remove(alternate)
    if selected is not None:
        for offset, node in enumerate(selected):
            parent.insert(index + offset, node)
