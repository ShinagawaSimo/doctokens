"""Dtx content."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.ooxml.charts.preview import append_chart_preview
from doctokens_core.output.diagram_preview import diagram_preview
from doctokens_core.output.xml import append, text

from ..model import InlineObject
from .objects.charts import preview_info


def _append_chart(parent: ET.Element, chart: InlineObject) -> None:
    node = append(
        parent, "chart", id=chart.get("id") if "series" in chart else None, type=chart.get("chartType"), title=chart.get("title")
    )
    if "series" not in chart:
        append(node, "unsupported", type="chart")
        return
    append_chart_preview(node, preview_info(chart))


def _append_smartart(parent: ET.Element, smartart: InlineObject) -> None:
    nodes = smartart.get("nodes", [])
    links = smartart.get("links", [])
    preview = diagram_preview(
        [(index, item["text"]) for index, item in enumerate(nodes, start=1)],
        [(edge["from"], edge["to"]) for edge in links],
    )
    node = append(
        parent,
        "smartart",
        id=smartart.get("id") if "nodes" in smartart else None,
        type=smartart.get("layoutType"),
        nodes=smartart.get("nodeCount"),
        links=smartart.get("linkCount"),
        truncated=True if preview.truncated else None,
        incomplete=True if smartart.get("rawLinkCount", 0) > smartart.get("linkCount", 0) else None,
    )
    if "nodes" not in smartart:
        append(node, "unsupported", type="smartart")
        return
    for item in preview.nodes:
        append(
            node, "node", item.text, id=item.id, kind=nodes[item.id - 1].get("kind"), truncated=True if item.truncated else None
        )
    for index in preview.link_indices:
        edge = links[index]
        append(node, "link", **{"from": edge["from"], "to": edge["to"], "kind": edge.get("kind")})


def _append_text_with_breaks(parent: ET.Element, value: str) -> None:
    fragments = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for line_index, line in enumerate(fragments):
        tab_fragments = line.split("\t")
        for tab_index, tab_fragment in enumerate(tab_fragments):
            text(parent, tab_fragment)
            if tab_index < len(tab_fragments) - 1:
                append(parent, "tab")
        if line_index < len(fragments) - 1:
            append(parent, "br")
