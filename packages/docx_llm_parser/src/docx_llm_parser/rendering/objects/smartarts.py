"""SmartArt inline rendering and extract helpers."""

from __future__ import annotations

from html import escape as escape_text

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
    """Render SmartArt as a self-defined output string for get_resource."""
    smartart_id = s.get("id", "?")
    attrs = f"id={smartart_id}"
    if s.get("layoutType"):
        attrs += f" type={s['layoutType']}"
    attrs += f" nodes={s.get('nodeCount', 0)} links={s.get('linkCount', 0)}"
    output_parts = [f"<smartart {attrs}>"]

    for node_index, node in enumerate(s.get("nodes") or [], start=1):
        node_attrs = f"index={node_index} text={escape_text(node.get('text', ''), quote=True)}"
        if node.get("kind"):
            node_attrs += f" kind={node['kind']}"
        output_parts.append(f"\n<node {node_attrs}/>")

    for connection in s.get("links") or []:
        connection_attrs = f"from={connection['from']} to={connection['to']}"
        if connection.get("kind"):
            connection_attrs += f" kind={connection['kind']}"
        output_parts.append(f"\n<link {connection_attrs}/>")

    return "".join(output_parts)
