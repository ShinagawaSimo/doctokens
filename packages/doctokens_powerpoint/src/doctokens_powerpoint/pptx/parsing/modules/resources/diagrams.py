"""Read saved diagram nodes before resolving their source-defined connections."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from ....model.presentation import SmartArtLink, SmartArtNode
from ....ooxml.namespaces import local_name, qualified_name


def parse_diagram_data(
    root: ET.Element, part: str, warnings: list[ParseWarning]
) -> tuple[list[SmartArtNode], list[SmartArtLink]]:
    nodes: list[SmartArtNode] = []
    node_map: dict[str, int] = {}
    for element in root.iter():
        if element.tag != qualified_name("dgm", "pt"):
            continue
        node: SmartArtNode = {
            "id": len(nodes) + 1,
            "text": "".join(item.text or "" for item in element.iter() if local_name(item.tag) == "t"),
        }
        model_id = element.get("modelId")
        if model_id:
            node["sourceId"] = model_id
            if model_id in node_map:
                warnings.append(ParseWarning("SMARTART_DUPLICATE_MODEL_ID", "Duplicate diagram node modelId", part))
            else:
                node_map[model_id] = node["id"]
        if kind := element.get("type"):
            node["kind"] = kind
        nodes.append(node)
    links: list[SmartArtLink] = []
    for element in root.iter():
        if element.tag != qualified_name("dgm", "cxn"):
            continue
        start = node_map.get(element.get("srcId") or "")
        end = node_map.get(element.get("destId") or "")
        if start is None or end is None:
            warnings.append(ParseWarning("SMARTART_UNRESOLVED_LINK", "dgm:cxn references unknown modelId", part))
            continue
        link: SmartArtLink = {"from": start, "to": end}
        if kind := element.get("type"):
            link["kind"] = kind
        links.append(link)
    return nodes, links
