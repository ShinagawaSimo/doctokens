"""Complete DTX envelopes for format-specific explanatory operations."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from .doctokens_xml import append, element, serialize


def operation_root(format_name: str, density: str = "semantic") -> ET.Element:
    names = {"docx": "document", "pptx": "presentation", "xlsx": "workbook"}
    return element(names[format_name], density=density, format=format_name)


def resource_document(format_name: str, resource: ET.Element) -> str:
    root = operation_root(format_name)
    append(root, "resources").append(resource)
    return serialize(root)
