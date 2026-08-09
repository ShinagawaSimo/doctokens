"""Atomic JSON/JSONL debug artifact writer."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol


class TextSink(Protocol):
    """Minimal text stream surface required by JSON serializers."""

    def write(self, value: str, /) -> int: ...


class DebugWriter:
    """Write parser intermediate state atomically to a debug directory."""

    def __init__(self, debug_dir: Path, enabled: bool = True) -> None:
        self.debug_dir = debug_dir
        self.enabled = enabled
        if self.enabled:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> DebugWriter:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    def write_json(self, filename: str, data: Any) -> None:
        if not self.enabled:
            return
        self._atomic_write(filename, lambda stream: json.dump(data, stream, ensure_ascii=False, indent=2))

    def write_jsonl(self, filename: str, rows: Iterable[Mapping[str, object]]) -> None:
        if not self.enabled:
            return

        def write_rows(stream: TextSink) -> None:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False))
                stream.write("\n")

        self._atomic_write(filename, write_rows)

    def _atomic_write(self, filename: str, write: Callable[[TextSink], object]) -> None:
        target = self.debug_dir / filename
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                write(stream)
                stream.flush()
                os.fsync(stream.fileno())
            temporary_path.replace(target)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
