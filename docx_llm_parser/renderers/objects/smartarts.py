"""SmartArt inline 渲染与 extract 辅助。"""

from __future__ import annotations

from html import escape

from ...core.models import InlineObject, ResourceDetail, SmartArt
from .. import _constants


def smartart_to_html5(obj: InlineObject) -> str:
    """L2：输出 SmartArt 节点和连接（使用语义属性名）。"""
    smartart_id = obj.get("id", "?")
    smartart_type = obj.get("layoutType", "")
    node_count = obj.get("nodeCount", 0)
    link_count = obj.get("linkCount", 0)

    attrs = f"id={smartart_id} type={smartart_type} nodes={node_count} links={link_count}"
    nodes = obj.get("nodes") or []
    links = obj.get("links") or []

    extract_hint = f'\n<!-- Use extract("smartart", "{smartart_id}") for full data. -->'

    if not nodes and not links:
        return f"<sa {attrs}>" + extract_hint

    parts = [f"<sa {attrs}>"]
    for index, node in enumerate(nodes[: _constants._SA_NODES_TRUNCATE], start=1):
        n_attrs = f"i={index}"
        if node.get("kind"):
            n_attrs += f" k={escape(node['kind'], quote=True)}"
        parts.append(f"<n {n_attrs}>{escape(node['text'])}</n>")
    if len(nodes) > _constants._SA_NODES_TRUNCATE:
        parts.append(f"<mn c={len(nodes) - _constants._SA_NODES_TRUNCATE}/>")
    for link in links[: _constants._SA_LINKS_TRUNCATE]:
        l_attrs = f"f={link['from']} t={link['to']}"
        if link.get("kind"):
            l_attrs += f" k={escape(link['kind'], quote=True)}"
        parts.append(f"<e {l_attrs}/>")
    if len(links) > _constants._SA_LINKS_TRUNCATE:
        parts.append(f"<ml c={len(links) - _constants._SA_LINKS_TRUNCATE}/>")
    parts.append("</sa>")
    parts.append(extract_hint)
    return "".join(parts)


def extract_smartart_item(s: SmartArt) -> ResourceDetail:
    """构建 extract("smartart") 的完整返回项。"""
    item: ResourceDetail = {
        "id": s.get("id", ""),
        "nodeCount": s.get("nodeCount", 0),
        "linkCount": s.get("linkCount", 0),
    }
    if s.get("layoutType"):
        item["type"] = s["layoutType"]
    nodes = s.get("nodes") or []
    item_nodes = []
    for i, n in enumerate(nodes, start=1):
        n_item: ResourceDetail = {"index": i, "text": n.get("text", "")}
        if n.get("kind"):
            n_item["kind"] = n["kind"]
        item_nodes.append(n_item)
    item["nodes"] = item_nodes
    links = s.get("links") or []
    item_links = []
    for link in links:
        link_item: ResourceDetail = {"from": link["from"], "to": link["to"]}
        if link.get("kind"):
            link_item["kind"] = link["kind"]
        item_links.append(link_item)
    item["links"] = item_links
    return item
