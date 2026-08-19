"""Small, density-neutral parser for Word structured document tags (``w:sdt``)."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.xml import local_attr, local_name

from ..core.constants import attr, first_child
from ..core.models import ContentControl, ContentControlOption

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


def parse_content_control(sdt: ET.Element) -> ContentControl:
    """Extract user-facing ``w:sdtPr`` semantics without walking ``sdtContent``.

    The content is parsed by the normal paragraph/run pipeline.  Keeping this
    helper metadata-only prevents a second traversal of potentially large
    controls and lets nested controls be represented as a stack on the
    existing block/run rather than duplicate content nodes.
    """
    properties = first_child(sdt, "w", "sdtPr")
    control: ContentControl = {"type": "contentControl", "controlType": "unknown"}
    if properties is None:
        return control

    for child in properties:
        name = local_name(child.tag)
        if name in _CONTROL_TYPES:
            control["controlType"] = _CONTROL_TYPES[name]
            if name in {"comboBox", "dropDownList"}:
                control["options"] = _parse_options(child)
            elif name == "date":
                date_format_node = first_child(child, "w", "dateFormat")
                date_format = attr(date_format_node, "w", "val") if date_format_node is not None else None
                if date_format:
                    control["dateFormat"] = date_format
            elif name == "checkbox":
                checked = local_attr(child, "checked")
                if checked is not None:
                    control["checked"] = _word_bool(checked)
            continue

        if name in {"alias", "tag", "id", "lock", "temporary"}:
            value = attr(child, "w", "val")
            if name == "alias" and value:
                control["alias"] = value
            elif name == "tag" and value:
                control["tag"] = value
            elif name == "id" and value:
                control["id"] = value
            elif name == "lock" and value:
                control["lock"] = value
            elif name == "temporary":
                control["temporary"] = _word_bool(value)
            continue

        if name == "placeholder":
            doc_part = first_child(child, "w", "docPart")
            placeholder = attr(doc_part, "w", "val") if doc_part is not None else None
            if placeholder:
                control["placeholder"] = placeholder
            continue

        if name == "dataBinding":
            binding: dict[str, str] = {}
            for key in ("xpath", "storeItemID", "prefixMappings"):
                value = attr(child, "w", key)
                if value:
                    binding[key] = value
            if binding:
                control["binding"] = binding
            continue

        if name == "text":
            multi_line = attr(child, "w", "multiLine")
            if multi_line is not None:
                control["multiLine"] = _word_bool(multi_line)

    return control


def _parse_options(container: ET.Element) -> list[ContentControlOption]:
    options: list[ContentControlOption] = []
    for child in container:
        if local_name(child.tag) != "listItem":
            continue
        display = attr(child, "w", "displayText") or ""
        value = attr(child, "w", "value") or display
        if not display and not value:
            continue
        item: ContentControlOption = {"display": display or value, "value": value}
        options.append(item)
    return options


def _word_bool(value: str | None) -> bool:
    return value is not None and value.lower() not in {"0", "false", "off", "none"}


__all__ = ["parse_content_control"]
