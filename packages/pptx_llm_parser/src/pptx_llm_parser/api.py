"""Convenience functions — accept source files directly, return rendered results."""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

from .core.enums import Density
from .core.models import ParseOptions
from .parser import PptxParser
from .renderers._render import iter_plain, iter_semantic, iter_structural

_DENSITY_FILENAMES = {
    Density.PLAIN: "plain.txt",
    Density.STRUCTURAL: "structural.html",
    Density.SEMANTIC: "parsed.html",
}


def parse_pptx(
    source: str | Path | bytes,
    *,
    density: Density | str = Density.SEMANTIC,
    stream: bool = False,
    options: ParseOptions | None = None,
) -> str | Iterator[str]:
    """Parse a PPTX file into LLM-readable markup."""
    resolved = Density.parse(density)
    if stream:
        raise NotImplementedError("stream=True is not implemented yet")
    parsed = PptxParser().parse(source, options or ParseOptions())
    if resolved == Density.PLAIN:
        return "".join(iter_plain(parsed))
    if resolved == Density.STRUCTURAL:
        return "".join(iter_structural(parsed))
    return "".join(iter_semantic(parsed))


def write_document(
    source: str | Path | bytes,
    output_dir: str | Path,
    *,
    density: Density | str = Density.SEMANTIC,
    options: ParseOptions | None = None,
) -> Path:
    """Render one density and atomically write the output file into output_dir."""
    resolved = Density.parse(density)
    text = parse_pptx(source, density=resolved, options=options)
    assert isinstance(text, str)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / _DENSITY_FILENAMES[resolved]
    fd, temp_name = tempfile.mkstemp(prefix=".parsed.", suffix=".tmp", dir=target_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as temp_file:
            temp_file.write(text)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)
        raise
    return target
