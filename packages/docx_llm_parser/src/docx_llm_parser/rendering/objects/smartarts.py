"""SmartArt inline rendering and extract helpers."""

from __future__ import annotations

from html import escape as escape_text

from ooxml_llm_core.doctokens_xml import append, element
from ooxml_llm_core.resource_xml import resource_document

from ...core.models import InlineObject, SmartArt


def smartart_to_output(inline_object: InlineObject) -> str:
    """Output a SmartArt summary: show all node text; the full structure is available via get_resource."""
    smartart_id = inline_object.get("id", "?")
    smartart_type = inline_object.get("layoutType", "")
    node_count = inline_object.get("nodeCount", 0)
    link_count = inline_object.get("linkCount", 0)

    attrs = f"id={smartart_id} type={smartart_type} nodes={node_count} links={link_count} truncated"

    nodes = inline_object.get("nodes") or []
    all_text = " ".join(node.get("text", "") for node in nodes)
    return f"<smartart {attrs}>{escape_text(all_text)}\n"


def render_smartart_resource(s: SmartArt) -> str:
    """Render the complete SmartArt resource in DTX."""
    node = element(
        "smartart",
        id=s.get("id", "?"),
        type=s.get("layoutType") or None,
        nodes=s.get("nodeCount", 0),
        links=s.get("linkCount", 0),
    )
    for index, item in enumerate(s.get("nodes") or [], start=1):
        append(node, "node", index=index, text=item.get("text", ""), kind=item.get("kind") or None)
    for link in s.get("links") or []:
        append(node, "link", **{"from": link["from"], "to": link["to"], "kind": link.get("kind") or None})
    return resource_document("docx", node)
