"""Read saved content-control labels, choices, state and editing restrictions."""

from __future__ import annotations

from typing import Literal
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.xml import local_name

from ..model import ContentControl
from .namespaces import attr, first_child

_W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
_CONTROL_TYPES = {
    "text": "text",
    "richText": "richText",
    "picture": "picture",
    "date": "date",
    "comboBox": "comboBox",
    "dropDownList": "dropDownList",
    "checkbox": "checkbox",
    "group": "group",
    "repeatingSection": "repeatingSection",
    "citation": "citation",
    "docPartList": "buildingBlock",
    "docPartObj": "buildingBlock",
}
_LOCKS: dict[str, Literal["content", "control", "both"]] = {
    "contentLocked": "content",
    "sdtLocked": "control",
    "sdtContentLocked": "both",
}


def parse_content_control(sdt: ET.Element) -> ContentControl:
    """Read useful metadata; ordinary readers retain the saved sdtContent."""
    control: ContentControl = {"controlType": "unknown"}
    properties = first_child(sdt, "w", "sdtPr")
    if properties is None:
        return control
    for child in properties:
        name = local_name(child.tag)
        if name in _CONTROL_TYPES:
            control["controlType"] = _CONTROL_TYPES[name]
            if name in {"comboBox", "dropDownList"}:
                control["options"] = _parse_options(child)
            elif child.tag == _W14 + "checkbox":
                checked = child.find(_W14 + "checked")
                value = checked.get(_W14 + "val", "").lower() if checked is not None else ""
                if value in {"1", "true", "on", "0", "false", "off"}:
                    control["checked"] = value in {"1", "true", "on"}
        elif name == "alias" and (label := attr(child, "w", "val")):
            control["label"] = label
        elif name == "lock":
            lock = _LOCKS.get(attr(child, "w", "val") or "")
            if lock is not None:
                control["lock"] = lock
    return control


def _parse_options(container: ET.Element) -> list[str]:
    options: list[str] = []
    for child in container:
        if local_name(child.tag) != "listItem":
            continue
        display = attr(child, "w", "displayText") or attr(child, "w", "value")
        if display and display not in options:
            options.append(display)
    return options


__all__ = ["parse_content_control"]
