"""DOCX native math objects in the selected revision view."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.ooxml.equations.converter import convert_math
from doctokens_core.ooxml.equations.results import RevisionView
from doctokens_core.ooxml.equations.text import WarningSink

from ....model import InlineObject


def equation_object(node: ET.Element, *, revision_mode: RevisionView = "final", warn: WarningSink | None = None) -> InlineObject:
    result = convert_math(node, revision_mode=revision_mode, warn=warn)
    obj: InlineObject = {"type": "equation", "text": result.text}
    if result.revisions:
        obj["mathRevisions"] = result.revisions
    return obj
