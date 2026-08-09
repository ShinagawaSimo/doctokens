"""Document-level concurrent parsing entry point."""

from __future__ import annotations

import os
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .core.enums import RevisionMode
from .core.models import ParseOptions
from .parser import DocxParser
from .renderers.html5 import write_outputs


@dataclass(frozen=True)
class BatchParseResult:
    """Summary of one DOCX batch parse task result."""

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
    revision_mode: RevisionMode | str = RevisionMode.FINAL,
) -> list[BatchParseResult]:
    """Concurrently parse multiple DOCX files, keeping results in input order."""
    if max_workers is not None and max_workers <= 0:
        raise ValueError("max_workers must be greater than zero")
    resolved_revision_mode = RevisionMode.parse(revision_mode)
    paths = [Path(item) for item in docx_paths]
    if not paths:
        return []

    worker_count = max_workers or min(32, (os.cpu_count() or 1) + 4, len(paths))
    results: list[BatchParseResult | None] = [None] * len(paths)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_parse_one, path, Path(output_base), resolved_revision_mode): index
            for index, path in enumerate(paths)
        }
        for future in as_completed(futures):
            # Each document's context is independent; completion order does not affect return order.
            results[futures[future]] = future.result()

    return [cast(BatchParseResult, item) for item in results]


def _parse_one(docx_path: Path, output_base: Path, revision_mode: RevisionMode) -> BatchParseResult:
    """Parse a single document; exceptions are folded into the batch result so others continue."""
    output_dir = output_base / docx_path.stem
    try:
        options = ParseOptions(debug=False, revision_mode=revision_mode, output_dir=output_dir)
        parsed = DocxParser().parse(docx_path, options)
        paths = write_outputs(parsed, output_dir)
        return BatchParseResult(
            docx=docx_path,
            output_dir=output_dir,
            ok=True,
            output_path=Path(paths["html"]),
            debug_dir=Path(parsed.debug_dir) if parsed.debug_dir is not None else None,
        )
    except Exception as exc:
        # Batch mode records per-document failures so one bad input does not block the queue.
        return BatchParseResult(
            docx=docx_path,
            output_dir=output_dir,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )
