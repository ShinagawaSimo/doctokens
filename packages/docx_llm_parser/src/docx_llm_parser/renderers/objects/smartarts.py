"""SmartArt inline rendering and extract helpers."""

from __future__ import annotations

from html import escape

from ...core.models import InlineObject, SmartArt


def smartart_to_html5(obj: InlineObject) -> str:
    """Output a SmartArt summary: show all node text; the full structure is available via get_resource."""
    smartart_id = obj.get("id", "?")
    smartart_type = obj.get("layoutType", "")
    node_count = obj.get("nodeCount", 0)
    link_count = obj.get("linkCount", 0)

    attrs = f"id={smartart_id} type={smartart_type} nodes={node_count} links={link_count} truncated"

    nodes = obj.get("nodes") or []
    all_text = " ".join(n.get("text", "") for n in nodes)
    return f"<smartart {attrs}>{escape(all_text)}\n"


def render_smartart_resource(s: SmartArt) -> str:
    """Render SmartArt as an HTML string for get_resource."""
    sa_id = s.get("id", "?")
    attrs = f"id={sa_id}"
    if s.get("layoutType"):
        attrs += f" type={s['layoutType']}"
    attrs += f" nodes={s.get('nodeCount', 0)} links={s.get('linkCount', 0)}"
    parts = [f"<smartart {attrs}>"]

    for i, n in enumerate(s.get("nodes") or [], start=1):
        n_attrs = f"index={i} text={escape(n.get('text', ''), quote=True)}"
        if n.get("kind"):
            n_attrs += f" kind={n['kind']}"
        parts.append(f"\n<node {n_attrs}/>")

    for link in s.get("links") or []:
        l_attrs = f'from={link["from"]} to={link["to"]}'
        if link.get("kind"):
            l_attrs += f" kind={link['kind']}"
        parts.append(f"\n<link {l_attrs}/>")

    return "".join(parts)
