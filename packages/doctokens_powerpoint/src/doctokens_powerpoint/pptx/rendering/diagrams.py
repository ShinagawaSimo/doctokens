"""Serialize source-defined diagram labels and edges without inferring a flow."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.output.diagram_preview import diagram_plain, diagram_preview
from doctokens_core.output.xml import append

from ..model.presentation import SmartArtRecord


def append_diagram(
    parent: ET.Element,
    record: SmartArtRecord,
    *,
    include_source_ids: bool = False,
    preview: bool = False,
) -> None:
    nodes, links = record.get("nodes", []), record.get("links", [])
    selected = (
        diagram_preview([(node["id"], node["text"]) for node in nodes], [(edge["from"], edge["to"]) for edge in links])
        if preview
        else None
    )
    if record.get("rawLinkCount", 0) > len(record.get("links", [])):
        parent.set("incomplete", "true")
    if selected is not None and selected.truncated:
        parent.set("truncated", "true")
    parent.attrib = dict(sorted(parent.attrib.items()))
    labels = {node.id: node for node in selected.nodes} if selected is not None else None
    for node in nodes:
        if labels is not None and node["id"] not in labels:
            continue
        label = labels[node["id"]] if labels is not None else None
        append(
            parent,
            "node",
            label.text if label is not None else node["text"],
            id=node["id"],
            source_id=node.get("sourceId") if include_source_ids else None,
            kind=node.get("kind"),
            truncated=True if label is not None and label.truncated else None,
        )
    for index in selected.link_indices if selected is not None else range(len(links)):
        edge = links[index]
        append(parent, "link", **{"from": edge["from"], "to": edge["to"], "kind": edge.get("kind")})


def diagram_text(record: SmartArtRecord) -> str:
    return diagram_plain(
        [node["text"] for node in record.get("nodes", [])],
        record.get("id"),
        link_count=len(record.get("links", [])),
    )
