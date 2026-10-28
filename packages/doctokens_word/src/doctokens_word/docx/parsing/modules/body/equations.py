"""DOCX math objects and saved deleted formulas in source order."""

from __future__ import annotations

from collections.abc import Callable
from xml.etree import ElementTree as ET

from doctokens_core.ooxml.equations.converter import convert_math
from doctokens_core.ooxml.equations.results import RevisionView
from doctokens_core.ooxml.equations.text import WarningSink

from ....model import InlineObject, Run
from ....ooxml.namespaces import local_name, qualified_name

_MATH = {qualified_name("m", "oMath"), qualified_name("m", "oMathPara")}
_TEXT = {qualified_name("w", "t"), qualified_name("w", "delText")}


def equation_object(node: ET.Element, *, revision_mode: RevisionView = "final", warn: WarningSink | None = None) -> InlineObject:
    result = convert_math(node, revision_mode=revision_mode, warn=warn)
    obj: InlineObject = {"type": "equation", "text": result.text}
    if result.revisions:
        obj["mathRevisions"] = result.revisions
    return obj


def deleted_math_runs(node: ET.Element, read_math: Callable[[ET.Element], InlineObject]) -> list[Run]:
    """Recover formula objects without flattening them into deleted-text runs."""
    runs: list[Run] = []

    def visit(element: ET.Element) -> None:
        if element.tag in _MATH:
            obj = read_math(element)
            if obj.get("text"):
                runs.append({"text": "", "objects": [obj]})
        elif element.tag in _TEXT:
            if element.text:
                runs.append({"text": element.text})
        elif local_name(element.tag).endswith("Pr"):
            return
        else:
            for child in element:
                visit(child)

    visit(node)
    return runs


def contains_math(node: ET.Element) -> bool:
    return any(element.tag in _MATH for element in node.iter())
