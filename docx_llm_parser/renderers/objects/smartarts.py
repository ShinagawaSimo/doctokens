"""SmartArt inline 渲染与 extract 辅助。"""

from __future__ import annotations

from html import escape

from ...core.models import InlineObject, ResourceDetail, SmartArt


def smartart_to_html5(obj: InlineObject) -> str:
    """输出 SmartArt 摘要：显示全部节点文本，完整结构通过 get_resource 获取。"""
    smartart_id = obj.get("id", "?")
    smartart_type = obj.get("layoutType", "")
    node_count = obj.get("nodeCount", 0)
    link_count = obj.get("linkCount", 0)

    attrs = f"id={smartart_id} type={smartart_type} nodes={node_count} links={link_count} truncated"

    nodes = obj.get("nodes") or []
    all_text = " ".join(n.get("text", "") for n in nodes)
    return f"<smartart {attrs}>{escape(all_text)}\n"


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
