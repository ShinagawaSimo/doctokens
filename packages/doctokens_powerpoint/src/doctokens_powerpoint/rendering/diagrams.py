"""Serialize source-defined diagram labels and edges without inferring a flow."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.doctokens_xml import append

from ..core.models import SmartArtRecord


def append_diagram(parent: ET.Element, record: SmartArtRecord, *, include_source_ids: bool = False) -> None:
    if record.get("rawLinkCount", 0) > len(record.get("links", [])):
        parent.set("incomplete", "true")
        parent.attrib = dict(sorted(parent.attrib.items()))
    for node in record.get("nodes", []):
        append(
            parent,
            "node",
            node["text"],
            id=node["id"],
            source_id=node.get("sourceId") if include_source_ids else None,
            kind=node.get("kind"),
        )
    for edge in record.get("links", []):
        append(parent, "link", **{"from": edge["from"], "to": edge["to"], "kind": edge.get("kind")})


def diagram_text(record: SmartArtRecord) -> str:
    nodes = [f"[{node['id']}] {node['text']}" for node in record.get("nodes", [])]
    edges = [f"[Link {edge['from']} -> {edge['to']}]" for edge in record.get("links", [])]
    return "\n".join([*nodes, *edges])
