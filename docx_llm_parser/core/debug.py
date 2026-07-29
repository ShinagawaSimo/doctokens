"""调试中间结果输出。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DebugWriter:
    """把解析中间状态写到 debug 目录。"""

    def __init__(self, debug_dir: Path, enabled: bool = True) -> None:
        self.debug_dir = debug_dir
        self.enabled = enabled
        if self.enabled:
            # debug 目录按文档隔离，避免并发解析互相覆盖。
            self.debug_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, filename: str, data: Any) -> None:
        """写普通 JSON 调试文件。"""
        if not self.enabled:
            return
        path = self.debug_dir / filename
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def write_jsonl(self, filename: str, rows: list[dict[str, Any]]) -> None:
        """写 JSONL 调试文件，适合事件流。"""
        if not self.enabled:
            return
        path = self.debug_dir / filename
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False))
                f.write("\n")
