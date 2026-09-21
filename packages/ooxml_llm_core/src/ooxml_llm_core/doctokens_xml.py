"""Small direct XML output primitives shared by format-specific renderers."""

from __future__ import annotations

from xml.etree import ElementTree as ET


def element(name: str, text: str | None = None, /, **attrs: object | None) -> ET.Element:
    """Create one DTX element with normalized string attributes."""
    node = ET.Element(name)
    for key, value in sorted(attrs.items()):
        if value is not None:
            node.set(key.replace("_", "-"), _attribute_value(value))
    if text is not None:
        node.text = text
    return node


def append(parent: ET.Element, name: str, text: str | None = None, /, **attrs: object | None) -> ET.Element:
    """Append a normalized child element and return it."""
    child = element(name, text, **attrs)
    parent.append(child)
    return child


def text(parent: ET.Element, value: str) -> None:
    """Append character data without inventing an extra wrapper element."""
    if not value:
        return
    if len(parent):
        parent[-1].tail = (parent[-1].tail or "") + value
    else:
        parent.text = (parent.text or "") + value


def serialize(root: ET.Element) -> str:
    """Serialize one complete DTX document after validating well-formed XML."""
    output = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    validate_xml(output)
    return output


def validate_xml(value: str) -> None:
    """Validate well-formed DTX and its mandatory root metadata."""
    root = ET.fromstring(value)
    if root.get("schema") != "doctokens-xml" or root.get("version") != "1.0":
        raise ValueError("DTX root must declare doctokens-xml version 1.0")


def _attribute_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


__all__ = ["append", "element", "serialize", "text", "validate_xml"]
