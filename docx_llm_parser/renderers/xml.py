"""输出面向大模型阅读的语义 XML。"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator

from ..core.models import ParsedDocument, ParseWarning


def write_outputs(parsed: ParsedDocument, output_dir: Path) -> dict[str, str]:
    """写出最终 XML，并在 debug metrics 中记录渲染耗时。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    # 清理旧版本主产物，避免用户误把 JSON/Markdown 当成当前最终输出。
    for stale_name in ("parsed.json", "readable.md"):
        stale = output_dir / stale_name
        if stale.exists():
            stale.unlink()
    xml_path = output_dir / "parsed.xml"
    start = perf_counter()
    output_chars = 0
    with xml_path.open("w", encoding="utf-8") as f:
        # 大文档按片段写出，避免额外持有完整 XML 字符串。
        for chunk in iter_llm_xml(parsed):
            output_chars += len(chunk)
            f.write(chunk)
    elapsed_ms = (perf_counter() - start) * 1000
    _record_render_metrics(parsed, xml_path, output_chars, elapsed_ms)
    _write_metrics_debug(parsed)
    return {"xml": str(xml_path)}


def _record_render_metrics(
    parsed: ParsedDocument, xml_path: Path, output_chars: int, elapsed_ms: float
) -> None:
    """把最终 XML 写出阶段的指标追加到 parsed.metrics。"""
    metrics = parsed.metrics
    stages = metrics.setdefault("stagesMs", {})
    counters = metrics.setdefault("counters", {})
    metrics.setdefault("parseTotalMs", metrics.get("totalMs", 0.0))
    metrics["totalMs"] = round(metrics["parseTotalMs"] + elapsed_ms, 3)
    stages["render_write"] = round(elapsed_ms, 3)
    counters["outputChars"] = output_chars
    counters["outputBytes"] = xml_path.stat().st_size
    counters["estimatedTokens"] = max(1, round(output_chars / 4))


def _write_metrics_debug(parsed: ParsedDocument) -> None:
    """渲染后重写 metrics.json，使其中包含输出阶段耗时。"""
    if not parsed.debug_dir:
        return
    try:
        path = Path(parsed.debug_dir) / "metrics.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(parsed.metrics, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        parsed.warnings.append(
            ParseWarning(
                level="warning",
                code="METRICS_WRITE_FAILED",
                message=f"Failed to write render metrics debug artifact: {exc}",
            )
        )


def to_llm_xml(parsed: ParsedDocument) -> str:
    """生成可渲染、可定位、低噪声的语义 XML。"""
    return "".join(iter_llm_xml(parsed))


def iter_llm_xml(parsed: ParsedDocument) -> Iterator[str]:
    """按片段生成语义 XML，供大文档流式写出。"""
    attrs = {
        "source": parsed.metadata["sourceFile"],
        "format": parsed.metadata["format"],
        "pageModel": "ooxml-hints",
    }
    yield '<?xml version="1.0" encoding="utf-8"?>\n'
    yield f"<document{attrs_to_xml(attrs)}>\n"
    yield "  <body>\n"
    for block_index, block in enumerate(parsed.blocks, start=1):
        # 最终 id 按可见 body block 连续分配，合并原先块级 n 的定位功能。
        for line in indent_lines(block_to_xml(block, f"b{block_index}"), 4):
            yield f"{line}\n"
    yield "  </body>\n"
    for line in indent_lines(assets_to_xml(parsed.assets), 2):
        yield f"{line}\n"
    for line in indent_lines(supplemental_to_xml(parsed), 2):
        yield f"{line}\n"
    yield "</document>\n"


def block_to_xml(block: dict[str, Any], block_id: str) -> list[str]:
    """把内部 block 转成最终 XML block。"""
    block_type = block["type"]
    if block_type == "heading":
        return paragraph_like_to_xml(block, "heading", block_id)
    if block_type == "paragraph":
        return paragraph_like_to_xml(block, "p", block_id)
    if block_type == "table":
        return table_to_xml(block, block_id)
    raise ValueError(f"Unsupported internal block type: {block_type}")


def paragraph_like_to_xml(block: dict[str, Any], tag: str, block_id: str) -> list[str]:
    """输出段落/标题；只保留定位和理解文本必要的信息。"""
    attrs: dict[str, Any] = {
        "id": block_id,
        "page": block["page"],
    }
    if tag == "heading":
        attrs["level"] = block["level"]

    content = inline_content_to_xml(block)
    return [f"<{tag}{attrs_to_xml(attrs)}>{content}</{tag}>"]


def inline_content_to_xml(block: dict[str, Any]) -> str:
    """把 run 文本、链接、图片、脚注引用等合成为段落内部 XML。"""
    if "runs" not in block:
        # --no-runs 模式下内部 block 明确只保留合并后的文本。
        return escape(block["text"])

    runs = merge_text_runs(block["runs"])
    if not runs:
        return escape(block["text"])

    parts: list[str] = []
    for run in runs:
        text = escape(run["text"])
        text = format_text_to_xml(text, format_for_output(run))
        if run.get("revision") == "inserted":
            # review 模式才会出现；final 模式不会额外包裹。
            text = f"<ins>{text}</ins>"
        elif run.get("revision") == "deleted":
            text = f"<del>{text}</del>"

        link = run.get("link")
        if link and text:
            # 对模型有用的是可点击/可理解目标，不输出 relationshipId。
            link_attrs = {"href": link.get("href"), "anchor": link.get("anchor")}
            text = f"<link{attrs_to_xml(link_attrs)}>{text}</link>"
        if text:
            parts.append(text)

        if "objects" in run:
            for obj in run["objects"]:
                parts.append(inline_object_to_xml(obj))
    return "".join(parts)


def format_for_output(run: dict[str, Any]) -> dict[str, Any]:
    """过滤 run 格式，避免把超链接默认样式重复输出。"""
    fmt = dict(run.get("format") or {})
    if run.get("link"):
        if fmt.get("color") in {"#0563C1", "#0000FF"}:
            fmt.pop("color", None)
        if fmt.get("underline") is True:
            fmt.pop("underline", None)
    return fmt


def merge_text_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并相邻且输出语义相同的纯文本 run，减少最终 XML 碎片。"""
    merged: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    pending_key: tuple | None = None

    for run in runs:
        if "objects" in run:
            if pending is not None:
                merged.append(pending)
                pending = None
                pending_key = None
            merged.append(run)
            continue

        text = run["text"]
        if not text:
            continue
        signature = run_output_signature(run)
        if pending is not None and pending_key == signature:
            pending["text"] += text
            continue
        if pending is not None:
            merged.append(pending)
        pending = {"text": text}
        for output_key in ("revision", "link", "format"):
            if output_key in run:
                pending[output_key] = run[output_key]
        pending_key = signature

    if pending is not None:
        merged.append(pending)
    return merged


def run_output_signature(run: dict[str, Any]) -> tuple:
    """生成 run 输出相关字段的稳定签名。"""
    link = tuple(sorted((run.get("link") or {}).items()))
    fmt = tuple(sorted((run.get("format") or {}).items()))
    return (run.get("revision"), link, fmt)


def format_text_to_xml(text: str, fmt: dict[str, Any] | None) -> str:
    """用轻量语义标签表达模型可能会被问到的文字格式。"""
    if not text or not fmt:
        return text
    if fmt.get("bg"):
        text = f"<bg{attrs_to_xml({'color': fmt.get('bg')})}>{text}</bg>"
    if fmt.get("highlight"):
        text = f"<mark{attrs_to_xml({'color': fmt.get('highlight')})}>{text}</mark>"
    if fmt.get("color"):
        text = f"<color{attrs_to_xml({'value': fmt.get('color')})}>{text}</color>"
    if fmt.get("strike"):
        text = f"<s>{text}</s>"
    if fmt.get("underline"):
        text = f"<u>{text}</u>"
    if fmt.get("italic"):
        text = f"<i>{text}</i>"
    if fmt.get("bold"):
        text = f"<b>{text}</b>"
    return text


def inline_object_to_xml(obj: dict[str, Any]) -> str:
    """输出段落内的非纯文本对象引用。"""
    obj_type = obj["type"]
    if obj_type == "image":
        attrs = {
            "ref": obj["assetId"],
            "file": obj.get("file"),
            "href": obj.get("href"),
            "placement": obj.get("placement"),
            "alt": obj.get("alt") or obj.get("title") or obj.get("name"),
        }
        return f"<image{attrs_to_xml(attrs)} />"
    if obj_type == "drawing":
        attrs = {
            "placement": obj.get("placement"),
            "alt": obj.get("alt") or obj.get("title") or obj.get("name"),
        }
        return f"<drawing{attrs_to_xml(attrs)} />"
    if obj_type == "textbox":
        attrs = {
            "placement": obj.get("placement"),
            "alt": obj.get("alt") or obj.get("title"),
        }
        return f"<textbox{attrs_to_xml(attrs)}>{escape(obj['text'])}</textbox>"
    if obj_type == "equation":
        if obj["text"]:
            return f"<eq>{escape(obj['text'])}</eq>"
        return "<eq />"
    if obj_type == "chart":
        return chart_to_xml(obj)
    if obj_type == "smartart":
        return smartart_to_xml(obj)
    if obj_type in {"footnoteRef", "endnoteRef", "commentRef"}:
        tag = {
            "footnoteRef": "footnote-ref",
            "endnoteRef": "endnote-ref",
            "commentRef": "comment-ref",
        }[obj_type]
        return f"<{tag}{attrs_to_xml({'id': obj['id']})} />"
    if obj_type == "fieldInstruction":
        # 字段指令对目录/页码/交叉引用排查有用，但不展开成大量内部结构。
        return f"<field instruction=\"{escape(obj['instruction'], quote=True)}\" />"
    raise ValueError(f"Unsupported inline object type: {obj_type}")


def chart_to_xml(obj: dict[str, Any]) -> str:
    """输出图表轻量摘要，避免内联完整工作簿数据。"""
    attrs = {
        "id": obj["id"],
        "kind": obj.get("chartType"),
        "title": obj.get("title"),
        "series": obj.get("seriesCount"),
        "points": obj.get("pointCount"),
    }
    series = obj.get("series") or []
    if not series:
        return f"<chart{attrs_to_xml(attrs)} />"

    parts = [f"<chart{attrs_to_xml(attrs)}>"]
    for item in series[:4]:
        # 每个系列只输出缓存数据 preview 和范围，满足趋势/大意类问答。
        series_attrs = {
            "name": item.get("name"),
            "points": item["pointCount"],
            "min": item.get("min"),
            "max": item.get("max"),
            "preview": item.get("preview"),
        }
        parts.append(f"<series{attrs_to_xml(series_attrs)} />")
    if len(series) > 4:
        parts.append(f"<more-series count=\"{len(series) - 4}\" />")
    parts.append("</chart>")
    return "".join(parts)


def smartart_to_xml(obj: dict[str, Any]) -> str:
    """输出 SmartArt 节点和连接的轻量结构。"""
    attrs = {
        "id": obj["id"],
        "nodes": obj.get("nodeCount"),
        "links": obj.get("linkCount"),
    }
    nodes = obj.get("nodes") or []
    links = obj.get("links") or []
    if not nodes and not links:
        return f"<smartart{attrs_to_xml(attrs)} />"

    parts = [f"<smartart{attrs_to_xml(attrs)}>"]
    for index, node in enumerate(nodes[:12], start=1):
        node_attrs = {"n": index, "kind": node.get("kind")}
        parts.append(f"<node{attrs_to_xml(node_attrs)}>{escape(node['text'])}</node>")
    if len(nodes) > 12:
        parts.append(f"<more-nodes count=\"{len(nodes) - 12}\" />")
    for link in links[:16]:
        link_attrs = {"from": link["from"], "to": link["to"], "kind": link.get("kind")}
        parts.append(f"<link-edge{attrs_to_xml(link_attrs)} />")
    if len(links) > 16:
        parts.append(f"<more-links count=\"{len(links) - 16}\" />")
    parts.append("</smartart>")
    return "".join(parts)


def table_to_xml(block: dict[str, Any], block_id: str) -> list[str]:
    """输出表格结构；简单表格和复杂表格都保持行列可读。"""
    attrs = {
        "id": block_id,
        "page": block["page"],
        "rows": len(block["rows"]),
        "cols": block["columnCount"],
    }
    lines = [f"<table{attrs_to_xml(attrs)}>"]
    for row in block["rows"]:
        row_attrs = {"n": row["rowIndex"] + 1}
        if row.get("isHeader"):
            row_attrs["role"] = "header"
        lines.append(f"  <row{attrs_to_xml(row_attrs)}>")
        for cell in row["cells"]:
            cell_attrs: dict[str, Any] = {
                "c": cell["colIndex"] + 1,
            }
            if cell["colSpan"] != 1:
                cell_attrs["colspan"] = cell["colSpan"]
            if cell["rowSpan"] != 1:
                cell_attrs["rowspan"] = cell["rowSpan"]
            if cell.get("vMerge"):
                cell_attrs["vmerge"] = cell["vMerge"]
            lines.append(f"    <cell{attrs_to_xml(cell_attrs)}>{cell_content_to_xml(cell)}</cell>")
        lines.append("  </row>")
    lines.append("</table>")
    return lines


def cell_content_to_xml(cell: dict[str, Any]) -> str:
    """输出单元格文本，尽量保留其中的轻量 inline 格式。"""
    blocks = cell["blocks"]
    if not blocks:
        return escape(cell["text"])
    parts: list[str] = []
    for block in blocks:
        if block["type"] in {"paragraph", "heading"}:
            parts.append(inline_content_to_xml(block))
        elif block["type"] == "table":
            # 嵌套表格也保留轻量行列结构，方便模型回答单元格内部表格问题。
            parts.append(nested_table_to_xml(block))
        else:
            raise ValueError(f"Unsupported cell block type: {block['type']}")
    return "<br />".join(part for part in parts if part)


def nested_table_to_xml(block: dict[str, Any]) -> str:
    """把单元格内嵌套表格渲染成无全局 id 的轻量 XML。"""
    attrs = {"rows": len(block["rows"]), "cols": block["columnCount"]}
    lines = [f"<nested-table{attrs_to_xml(attrs)}>"]
    for row in block["rows"]:
        row_attrs = {"n": row["rowIndex"] + 1}
        if row.get("isHeader"):
            row_attrs["role"] = "header"
        lines.append(f"<row{attrs_to_xml(row_attrs)}>")
        for cell in row["cells"]:
            cell_attrs: dict[str, Any] = {"c": cell["colIndex"] + 1}
            if cell["colSpan"] != 1:
                cell_attrs["colspan"] = cell["colSpan"]
            if cell["rowSpan"] != 1:
                cell_attrs["rowspan"] = cell["rowSpan"]
            if cell.get("vMerge"):
                cell_attrs["vmerge"] = cell["vMerge"]
            lines.append(f"<cell{attrs_to_xml(cell_attrs)}>{cell_content_to_xml(cell)}</cell>")
        lines.append("</row>")
    lines.append("</nested-table>")
    return "".join(lines)


def assets_to_xml(assets: list[dict[str, Any]]) -> list[str]:
    """输出图片等资源清单，正文通过 ref 引用这里的 id。"""
    if not assets:
        return []
    lines = ["<assets>"]
    for asset in assets:
        if asset["type"] == "image":
            attrs = {
                "id": asset["id"],
                "file": asset.get("file"),
                "href": asset.get("href"),
                "contentType": asset.get("contentType"),
                "sizeBytes": asset.get("sizeBytes"),
            }
            lines.append(f"  <image{attrs_to_xml(attrs)} />")
        else:
            raise ValueError(f"Unsupported asset type: {asset['type']}")
    lines.append("</assets>")
    return lines


def supplemental_to_xml(parsed: ParsedDocument) -> list[str]:
    """输出正文之外的补充文本，避免混入主阅读流。"""
    groups = [
        ("headers", "header", parsed.headers),
        ("footers", "footer", parsed.footers),
        ("footnotes", "note", parsed.footnotes),
        ("endnotes", "note", parsed.endnotes),
        ("comments", "comment", parsed.comments),
    ]
    if not any(items for _group, _tag, items in groups):
        return []

    lines = ["<supplemental>"]
    for group_name, tag, items in groups:
        if not items:
            continue
        lines.append(f"  <{group_name}>")
        for item in items:
            attrs = {
                "id": item["id"],
                "loc": item.get("loc"),
                "author": item.get("author"),
                "date": item.get("date"),
            }
            lines.append(
                f"    <{tag}{attrs_to_xml(attrs)}>{inline_content_to_xml(item)}</{tag}>"
            )
        lines.append(f"  </{group_name}>")
    lines.append("</supplemental>")
    return lines


def attrs_to_xml(attrs: dict[str, Any]) -> str:
    """把属性字典转成 XML 属性字符串，过滤空值。"""
    parts: list[str] = []
    for key, value in attrs.items():
        if value is None or value == "":
            continue
        parts.append(f'{key}="{escape(str(value), quote=True)}"')
    return (" " + " ".join(parts)) if parts else ""


def indent_lines(lines: list[str], spaces: int) -> list[str]:
    """给多行 XML 增加缩进。"""
    prefix = " " * spaces
    return [prefix + line for line in lines]
