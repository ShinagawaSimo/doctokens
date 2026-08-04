"""渲染器共享的文本处理逻辑。

run 合并、签名计算、格式过滤是纯数据转换，
不依赖具体的输出标签语法。两个渲染器共用。"""

from __future__ import annotations

from ..core.models import Run, RunFormat

RunSignature = tuple[
    object,
    tuple[tuple[str, str], ...],
    tuple[tuple[str, bool | str | None], ...],
]


def merge_text_runs(runs: list[Run]) -> list[Run]:
    """合并相邻且输出语义相同的纯文本 run，减少最终输出碎片。"""
    merged: list[Run] = []
    pending: Run | None = None
    pending_key: RunSignature | None = None

    for run in runs:
        # 包含内联对象的 run 不参与合并，直接放入结果。
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
        if "revision" in run:
            pending["revision"] = run["revision"]
        if "link" in run:
            pending["link"] = run["link"]
        if "format" in run:
            pending["format"] = run["format"]
        pending_key = signature

    if pending is not None:
        merged.append(pending)
    return merged


def run_output_signature(run: Run) -> RunSignature:
    """生成 run 输出相关字段的稳定签名，用于判断相邻 run 是否可合并。"""
    link: tuple[tuple[str, str], ...] = ()
    if "link" in run:
        link_items: list[tuple[str, str]] = []
        if "href" in run["link"]:
            link_items.append(("href", run["link"]["href"]))
        if "anchor" in run["link"]:
            link_items.append(("anchor", run["link"]["anchor"]))
        link = tuple(sorted(link_items))
    fmt = tuple(sorted((run.get("format") or {}).items()))
    return (run.get("revision"), link, fmt)


def filter_format(run: Run) -> RunFormat:
    """过滤 run 格式，移除超链接的默认样式（蓝色+下划线）避免输出噪声。"""
    fmt = dict(run.get("format") or {})
    if run.get("link"):
        if fmt.get("color") in {"#0563C1", "#0000FF"}:
            fmt.pop("color", None)
        if fmt.get("underline") is True:
            fmt.pop("underline", None)
    return fmt
