"""SmartArt inline rendering and extract helpers."""

from __future__ import annotations

from doctokens_core.output.resources import resource_document
from doctokens_core.output.xml import append, element

from ...model import SmartArt


def render_smartart_resource(s: SmartArt) -> str:
    """Render the complete SmartArt resource in DTX."""
    node = element(
        "smartart",
        id=s.get("id", "?"),
        type=s.get("layoutType") or None,
        nodes=s.get("nodeCount", 0),
        links=s.get("linkCount", 0),
        incomplete=True if s.get("rawLinkCount", 0) > len(s.get("links", [])) else None,
    )
    for index, item in enumerate(s.get("nodes") or [], start=1):
        append(node, "node", index=index, text=item.get("text", ""), kind=item.get("kind") or None)
    for link in s.get("links") or []:
        append(node, "link", **{"from": link["from"], "to": link["to"], "kind": link.get("kind") or None})
    return resource_document("docx", node)
