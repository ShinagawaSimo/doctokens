"""输出面向大模型阅读的 HTML5 语义标记。

利用 HTML5 隐式闭合规则：块级元素（<p>、<h1>~<h6>、<table>、<tr>、<th>、<td>）
遇到下一个块元素时自动关闭，无需显式闭合标签。

inline 元素（<a>、<b>、<i>、<u>、<s>、<c>、<m>、<eq>）保留闭合标签，
因为链接/格式文本的边界必须显式标记。

与 XML 相比实际节省约 31% token（4.5MB docx 实测）：
- 块级闭合标签全部消除
- 单字符属性名（i=id, g=page, h=href, v=value, s=size/span, f=file, m=mime）
- 标签名缩短（heading→h2, link→a, paragraph→p）
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator

from ..core.models import ParsedDocument
from ._metrics import record_render_metrics, write_metrics_debug
from ._text_utils import filter_format, merge_text_runs, run_output_signature


def write_outputs(parsed: ParsedDocument, output_dir: Path) -> dict[str, str]:
    """写出最终 HTML5 标记，并在 metrics 中记录渲染耗时。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    # 清理旧版本产物，避免混淆。
    for stale_name in ("readable.md", "parsed.json"):
        stale = output_dir / stale_name
        if stale.exists():
            stale.unlink()
    html_path = output_dir / "parsed.html"
    start = perf_counter()
    output_chars = 0
    with html_path.open("w", encoding="utf-8") as f:
        for chunk in iter_html5(parsed):
            output_chars += len(chunk)
            f.write(chunk)
    elapsed_ms = (perf_counter() - start) * 1000
    record_render_metrics(parsed, html_path, output_chars, elapsed_ms)
    write_metrics_debug(parsed)
    return {"html": str(html_path)}


def to_html5(parsed: ParsedDocument) -> str:
    """生成完整 HTML5 标记字符串。"""
    return "".join(iter_html5(parsed))


def iter_html5(parsed: ParsedDocument) -> Iterator[str]:
    """按片段生成 HTML5 标记，供大文档流式写出。"""
    # 文档来源标识，LLM 可用于引用原始文件名。
    yield f'<!-- source="{escape(parsed.metadata["sourceFile"], quote=True)}" -->\n\n'

    # 正文块
    for block in parsed.blocks:
        for line in block_to_html5(block):
            yield line + "\n"

    # 资源清单
    yield "\n"
    for line in _assets_to_html5(parsed.assets):
        yield line + "\n"

    # 补充内容
    supplemental = _supplemental_to_html5(parsed)
    if supplemental:
        yield "\n"
        for line in supplemental:
            yield line + "\n"


# ── Block 渲染 ──

def block_to_html5(block: dict[str, Any]) -> list[str]:
    """把内部 block 转成 HTML5 块元素。"""
    block_type = block["type"]
    page = block["page"]
    block_id = block["id"]

    if block_type == "heading":
        level = min(block.get("level", 1), 6)
        tag = f"h{level}"
        text = _inline_content(block)
        return [f'<{tag} i={block_id} g={page}>{text}']

    if block_type == "paragraph":
        text = _inline_content(block)
        return [f'<p i={block_id} g={page}>{text}']

    if block_type == "table":
        return _table_to_html5(block)

    return [f'<p i={block_id} g={page}>[未知块类型: {block_type}]']


def _table_to_html5(block: dict[str, Any]) -> list[str]:
    """输出 HTML5 表格，利用 <th>/<td> 隐式闭合和 colspan/rowspan 属性。"""
    rows = block["rows"]
    lines = [f'<table i={block["id"]} g={block["page"]}>']
    for row in rows:
        row_tag = "<tr h>" if row.get("isHeader") else "<tr>"
        lines.append(row_tag)
        for cell in row["cells"]:
            cell_tag = "th" if row.get("isHeader") else "td"
            attrs_parts: list[str] = [f'{cell_tag}']
            if cell["colSpan"] != 1:
                attrs_parts.append(f's={cell["colSpan"]}')
            if cell["rowSpan"] != 1:
                attrs_parts.append(f'rs={cell["rowSpan"]}')
            if cell.get("vMerge"):
                attrs_parts.append(f'v={cell["vMerge"]}')
            attrs = " ".join(attrs_parts)
            cell_text = _cell_content(cell)
            lines.append(f'<{attrs}>{cell_text}')
    return lines


def _cell_content(cell: dict[str, Any]) -> str:
    """输出单元格文本，保留内嵌段落换行。"""
    blocks = cell.get("blocks", [])
    if not blocks:
        return escape(cell["text"])
    # 单元格中的多个段落用 <br> 分隔（<br> 是自闭合空元素）。
    parts: list[str] = []
    for block in blocks:
        if block["type"] in {"paragraph", "heading"}:
            parts.append(_inline_content(block))
        elif block["type"] == "table":
            # 嵌套表格保留轻量行列结构。
            parts.append(_nested_table(block))
    return "<br>".join(part for part in parts if part)


def _nested_table(block: dict[str, Any]) -> str:
    """把嵌套表格渲染为轻量 HTML5。"""
    rows = block["rows"]
    parts = [f'<ntable r={len(rows)} c={block["columnCount"]}>']
    for row in rows:
        tag = "<r h>" if row.get("isHeader") else "<r>"
        parts.append(tag)
        for cell in row["cells"]:
            c_tag = "th" if row.get("isHeader") else "td"
            attrs_parts: list[str] = [c_tag]
            if cell["colSpan"] != 1:
                attrs_parts.append(f's={cell["colSpan"]}')
            if cell["rowSpan"] != 1:
                attrs_parts.append(f'rs={cell["rowSpan"]}')
            if cell.get("vMerge"):
                attrs_parts.append(f'v={cell["vMerge"]}')
            attrs = " ".join(attrs_parts)
            parts.append(f"<{attrs}>{_cell_content(cell)}")
    return "".join(parts)


# ── Inline 内容渲染 ──

def _inline_content(block: dict[str, Any]) -> str:
    """把 run 文本、链接、图片、脚注引用等合成为 inline HTML5。
    块级元素不需要闭合标签，但 inline 元素（a/b/i/u/s/c/m/eq）需要。"""
    if "runs" not in block:
        return escape(block["text"])

    runs = merge_text_runs(block["runs"])
    if not runs:
        return escape(block["text"])

    parts: list[str] = []
    for run in runs:
        text = escape(run["text"])
        fmt = filter_format(run)
        text = _apply_inline_format(text, fmt)

        if run.get("revision") == "inserted":
            text = f"<ins>{text}</ins>"
        elif run.get("revision") == "deleted":
            text = f"<del>{text}</del>"

        link = run.get("link")
        if link and text:
            href = link.get("href", "")
            anchor = link.get("anchor", "")
            attrs = f'h={escape(href, quote=True)}'
            if anchor:
                attrs += f' a={escape(anchor, quote=True)}'
            text = f"<a {attrs}>{text}</a>"
        if text:
            parts.append(text)

        if "objects" in run:
            for obj in run["objects"]:
                parts.append(_inline_object(obj))
    return "".join(parts)


def _apply_inline_format(text: str, fmt: dict[str, Any]) -> str:
    """用 HTML5 inline 标签包裹格式化文本。
    标签嵌套顺序从外到内：bg > mark > color > s > u > i > b。"""
    if not text or not fmt:
        return text
    # 从外到内包裹
    if fmt.get("bg"):
        text = f'<m v={fmt["bg"]}>{text}</m>'
    if fmt.get("highlight"):
        text = f'<m v={fmt["highlight"]}>{text}</m>'
    if fmt.get("color"):
        text = f'<c v={fmt["color"]}>{text}</c>'
    if fmt.get("strike"):
        text = f"<s>{text}</s>"
    if fmt.get("underline"):
        text = f"<u>{text}</u>"
    if fmt.get("italic"):
        text = f"<i>{text}</i>"
    if fmt.get("bold"):
        text = f"<b>{text}</b>"
    return text


def _inline_object(obj: dict[str, Any]) -> str:
    """渲染段落内的非纯文本对象引用。"""
    obj_type = obj["type"]

    if obj_type == "image":
        attrs = f'i={obj.get("assetId","")} f={escape(obj.get("file",""), quote=True)}'
        if obj.get("alt"):
            attrs += f' alt={escape(obj["alt"], quote=True)}'
        return f"<img {attrs}>"

    if obj_type == "drawing":
        alt = obj.get("alt") or obj.get("title") or obj.get("name") or ""
        return f'<img alt={escape(alt, quote=True)}>' if alt else "<img>"

    if obj_type == "textbox":
        alt = obj.get("alt") or obj.get("title") or ""
        attrs = f'alt={escape(alt, quote=True)}' if alt else ""
        return f"<tb {attrs}>{escape(obj['text'])}</tb>"

    if obj_type == "equation":
        if obj["text"]:
            return f"<eq>{escape(obj['text'])}</eq>"
        return "<eq/>"

    if obj_type == "chart":
        return _chart_to_html5(obj)

    if obj_type == "smartart":
        return _smartart_to_html5(obj)

    if obj_type == "footnoteRef":
        return f'<fnr id={obj["id"]}/>'
    if obj_type == "endnoteRef":
        return f'<enr id={obj["id"]}/>'
    if obj_type == "commentRef":
        return f'<cmr id={obj["id"]}/>'

    if obj_type == "fieldInstruction":
        return f'<fld i={escape(obj["instruction"], quote=True)}/>'

    # 未知对象类型：保留轻量占位
    return f"<obj t={escape(obj_type, quote=True)}/>"


def _chart_to_html5(obj: dict[str, Any]) -> str:
    """输出图表轻量摘要。"""
    attrs = f'i={obj["id"]} k={obj.get("chartType","?")}'
    if obj.get("title"):
        attrs += f' t={escape(obj["title"], quote=True)}'
    attrs += f' s={obj.get("seriesCount",0)} p={obj.get("pointCount",0)}'

    series = obj.get("series") or []
    if not series:
        return f"<chart {attrs}/>"

    parts = [f"<chart {attrs}>"]
    for item in series[:4]:
        s_attrs = f'n={escape(item.get("name","?"), quote=True)} p={item["pointCount"]}'
        if "min" in item:
            s_attrs += f' min={item["min"]}'
        if "max" in item:
            s_attrs += f' max={item["max"]}'
        if item.get("preview"):
            s_attrs += f' pv={escape(item["preview"], quote=True)}'
        parts.append(f"<s {s_attrs}/>")
    if len(series) > 4:
        parts.append(f"<ms c={len(series)-4}/>")
    parts.append("</chart>")
    return "".join(parts)


def _smartart_to_html5(obj: dict[str, Any]) -> str:
    """输出 SmartArt 节点和连接。"""
    attrs = f'i={obj["id"]} n={obj.get("nodeCount",0)} l={obj.get("linkCount",0)}'
    nodes = obj.get("nodes") or []
    links = obj.get("links") or []
    if not nodes and not links:
        return f"<sa {attrs}/>"

    parts = [f"<sa {attrs}>"]
    for index, node in enumerate(nodes[:12], start=1):
        n_attrs = f"i={index}"
        if node.get("kind"):
            n_attrs += f' k={escape(node["kind"], quote=True)}'
        parts.append(f'<n {n_attrs}>{escape(node["text"])}</n>')
    if len(nodes) > 12:
        parts.append(f"<mn c={len(nodes)-12}/>")
    for link in links[:16]:
        l_attrs = f'f={link["from"]} t={link["to"]}'
        if link.get("kind"):
            l_attrs += f' k={escape(link["kind"], quote=True)}'
        parts.append(f"<e {l_attrs}/>")
    if len(links) > 16:
        parts.append(f"<ml c={len(links)-16}/>")
    parts.append("</sa>")
    return "".join(parts)


# ── 资源与补充内容 ──

def _assets_to_html5(assets: list[dict[str, Any]]) -> list[str]:
    """输出图片等资源清单，正文通过 img ref 引用。"""
    if not assets:
        return []
    lines = ["<!-- assets -->"]
    for asset in assets:
        if asset["type"] != "image":
            raise ValueError(f"Unsupported asset type: {asset['type']}")
        # 只输出 AI 理解任务需要的最小元数据：ID + 文件路径。
        # 尺寸/格式等可由下游工具直接从文件读取。
        attrs = f'i={asset["id"]}'
        if asset.get("file"):
            attrs += f' f={escape(asset["file"], quote=True)}'
        if asset.get("href"):
            attrs += f' h={escape(asset["href"], quote=True)}'
        if asset.get("contentType"):
            attrs += f' m={escape(asset["contentType"], quote=True)}'
        lines.append(f"<img {attrs}>")
    return lines


def _supplemental_to_html5(parsed: ParsedDocument) -> list[str]:
    """输出正文之外的补充文本，不混入主阅读流。"""
    groups = [
        ("headers", "hdr", parsed.headers),
        ("footers", "ftr", parsed.footers),
        ("footnotes", "fn", parsed.footnotes),
        ("endnotes", "en", parsed.endnotes),
        ("comments", "cm", parsed.comments),
    ]
    if not any(items for _group, _tag, items in groups):
        return []

    lines = ["<!-- supplemental -->"]
    for _group_name, tag, items in groups:
        if not items:
            continue
        for item in items:
            attrs = f'id={item["id"]}'
            if item.get("loc"):
                attrs += f' loc={escape(item["loc"], quote=True)}'
            if item.get("author"):
                attrs += f' a={escape(item["author"], quote=True)}'
            if item.get("date"):
                attrs += f' d={escape(item["date"], quote=True)}'
            content = _inline_content(item)
            lines.append(f"<{tag} {attrs}>{content}")
    return lines
