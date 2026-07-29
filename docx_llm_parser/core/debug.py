"""调试中间结果输出，支持异步写入减少主线程阻塞。"""

from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any


class DebugWriter:
    """把解析中间状态写到 debug 目录。
    优化：支持异步写入模式，debug JSON 序列化和磁盘 I/O 不阻塞主解析流程。
    使用 ThreadPoolExecutor(max_workers=1) 单后台线程顺序写入，
    避免多线程竞争 JSON 序列化顺序。"""

    def __init__(self, debug_dir: Path, enabled: bool = True) -> None:
        self.debug_dir = debug_dir
        self.enabled = enabled
        self._async: bool = False
        self._executor: ThreadPoolExecutor | None = None
        self._futures: list[Future] = []
        if self.enabled:
            # debug 目录按文档隔离，避免并发解析互相覆盖。
            self.debug_dir.mkdir(parents=True, exist_ok=True)

    # ── 异步模式入口 ──

    def enable_async(self) -> None:
        """开启异步写入模式：后续所有 write 调用提交到后台线程。
        必须在解析开始前调用，解析结束后调用 wait_all() 确保落盘。"""
        if not self.enabled:
            return
        self._async = True
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="debug_writer")

    def wait_all(self) -> None:
        """等待所有异步写入任务完成，关闭后台线程。
        在最终渲染输出之前调用，确保 debug 数据完整落盘。"""
        if not self._async or self._executor is None:
            return
        for future in self._futures:
            # 单个文件写入失败不应影响整体，仅静默吞掉异常。
            try:
                future.result()
            except Exception:
                pass
        self._futures.clear()
        self._executor.shutdown(wait=True)
        self._executor = None
        self._async = False

    # ── 写入方法 ──

    def write_json(self, filename: str, data: Any) -> None:
        """写普通 JSON 调试文件。"""
        if not self.enabled:
            return
        if self._async and self._executor is not None:
            # 异步模式：提交到后台线程，不阻塞主解析流程。
            self._futures.append(
                self._executor.submit(self._write_json_sync, filename, data)
            )
        else:
            self._write_json_sync(filename, data)

    def write_jsonl(self, filename: str, rows: list[dict[str, Any]]) -> None:
        """写 JSONL 调试文件，适合事件流。"""
        if not self.enabled:
            return
        if self._async and self._executor is not None:
            self._futures.append(
                self._executor.submit(self._write_jsonl_sync, filename, rows)
            )
        else:
            self._write_jsonl_sync(filename, rows)

    # ── 同步写入实现（异步模式复用同一实现） ──

    def _write_json_sync(self, filename: str, data: Any) -> None:
        """同步 JSON 写入实现。"""
        path = self.debug_dir / filename
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _write_jsonl_sync(self, filename: str, rows: list[dict[str, Any]]) -> None:
        """同步 JSONL 写入实现。"""
        path = self.debug_dir / filename
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False))
                f.write("\n")
