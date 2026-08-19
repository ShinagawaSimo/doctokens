"""OOXML XML helpers with configurable namespace maps.

The OPC-generic ``NS`` map is the default. Format-specific parsers pass
their own extended namespace map to the helper functions.
"""

from __future__ import annotations

from collections.abc import Mapping
from xml.etree import ElementTree as ET

# OPC-generic namespaces (package-level).
NS: Mapping[str, str] = {
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


def qualified_name(prefix: str, local: str, ns: Mapping[str, str] = NS) -> str:
    """Generate an ElementTree Clark-notation tag name using the given ns map."""
    return f"{{{ns[prefix]}}}{local}"


def local_name(tag: str) -> str:
    """Extract the local name from a namespace-qualified tag. Uses rfind for speed."""
    brace = tag.rfind("}")
    if brace != -1:
        return tag[brace + 1 :]
    return tag


def local_attr(el: ET.Element, local: str, default: str | None = None) -> str | None:
    """Read an attribute by local name when its extension namespace varies.

    Office versioned extension parts routinely use distinct namespace prefixes
    for the same logical attribute (for example ``paraId``).  The caller has
    already identified the extension element, so matching its local attribute
    name is both interoperable and more useful than serializing namespace IDs.
    """
    for name, value in el.attrib.items():
        if local_name(name) == local:
            return value
    return default


def attr(
    el: ET.Element,
    prefix: str,
    local: str,
    default: str | None = None,
    ns: Mapping[str, str] = NS,
) -> str | None:
    """Read a namespace-qualified XML attribute with an optional default."""
    return el.get(qualified_name(prefix, local, ns), default)


def first_child(
    el: ET.Element | None,
    prefix: str,
    local: str,
    ns: Mapping[str, str] = NS,
) -> ET.Element | None:
    """Find the first direct child with the given qualified name."""
    if el is None:
        return None
    wanted = qualified_name(prefix, local, ns)
    for child in el:
        if child.tag == wanted:
            return child
    return None


def child_elements(
    el: ET.Element | None,
    prefix: str,
    local: str,
    ns: Mapping[str, str] = NS,
) -> list[ET.Element]:
    """Find all direct children with the given qualified name."""
    if el is None:
        return []
    wanted = qualified_name(prefix, local, ns)
    return [child for child in el if child.tag == wanted]
