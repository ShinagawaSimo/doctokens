"""Explicit saved-image text resource, independent of host document densities."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ..containers.opc.reader import PackageReader
from ..ooxml.emf import MAX_CHARACTERS, read_emf_text
from .resources import resource_document
from .xml import append, element


def image_text_resource(package: PackageReader, part: str, resource_id: str, format_name: str) -> str:
    size = next((entry["uncompressedSize"] for entry in package.read_entry_index() if entry["name"] == part), 0)
    with package.open_entry(part) as stream:
        result = read_emf_text(stream, size)
    node = element("image-text", source=resource_id, format="emf" if result.recognized else None)
    used = 0
    for segment in result.segments:
        child = (
            element("text", segment["text"])
            if "text" in segment
            else element("unsupported", type="emf-text", reason=segment.get("reason"))
        )
        length = len(ET.tostring(child, encoding="unicode").replace("\r", "&#13;"))
        if used + length > MAX_CHARACTERS - 1024:
            result.limit("character-limit")
            if "text" in segment:
                available = MAX_CHARACTERS - 1024 - used
                value = segment["text"]
                low, high = 0, len(value)
                while low < high:
                    middle = (low + high + 1) // 2
                    candidate = element("text", value[:middle])
                    if len(ET.tostring(candidate, encoding="unicode").replace("\r", "&#13;")) <= available:
                        low = middle
                    else:
                        high = middle - 1
                if low:
                    node.append(element("text", value[:low]))
            break
        node.append(child)
        used += length
    for reason in result.limitations:
        append(node, "limitation", code=reason)
    if result.limitations:
        node.set("partial", "true")
    if not any(child.tag in {"text", "unsupported"} for child in node) and result.limitations:
        append(node, "unsupported", type="image-text")
    return resource_document(format_name, node)
