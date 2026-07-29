"""文档级并发解析入口。"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, cast

from .core.models import ParseOptions
from .parser import DocxParser
from .renderers.html5 import write_outputs


@dataclass(frozen=True)
class BatchParseResult:
    """单个 DOCX 批量解析任务的结果摘要。"""

    docx: Path
    output_dir: Path
    ok: bool
    output_path: Path | None = None
    debug_dir: Path | None = None
    error: str | None = None


def parse_many(
    docx_paths: Iterable[str | Path],
    output_base: str | Path,
    *,
    max_workers: int | None = None,
    revision_mode: str = "final",
) -> list[BatchParseResult]:
    """并发解析多篇 DOCX，并保持返回结果与输入顺序一致。"""
    paths = [Path(item) for item in docx_paths]
    if not paths:
        return []

    worker_count = max_workers or min(32, (os.cpu_count() or 1) + 4, len(paths))
    results: list[BatchParseResult | None] = [None] * len(paths)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_parse_one, path, Path(output_base), revision_mode): index
            for index, path in enumerate(paths)
        }
        for future in as_completed(futures):
            # 每篇文档上下文独立，完成顺序不影响最终返回顺序。
            results[futures[future]] = future.result()

    return [cast(BatchParseResult, item) for item in results]


def _parse_one(
    docx_path: Path, output_base: Path, revision_mode: str
) -> BatchParseResult:
    """解析单篇文档；异常被收敛为批量结果，便于其它文档继续完成。"""
    output_dir = output_base / docx_path.stem
    try:
        # debug 当前阶段常开，每个 worker 使用独立输出目录和解析上下文。
        options = ParseOptions(debug=True, revision_mode=revision_mode, output_dir=output_dir)
        parsed = DocxParser().parse(docx_path, options)
        paths = write_outputs(parsed, output_dir)
        return BatchParseResult(
            docx=docx_path,
            output_dir=output_dir,
            ok=True,
            output_path=Path(paths["html"]),
            debug_dir=Path(parsed.debug_dir),
        )
    except Exception as exc:
        # 批量模式记录单文档失败，不让一个坏输入阻断整个队列。
        return BatchParseResult(
            docx=docx_path,
            output_dir=output_dir,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )
