"""Convenience functions — accept source files directly, return rendered results."""

from __future__ import annotations

import contextlib
import dataclasses
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

from .core.enums import Density, ResourceType
from .core.models import ParseOptions
from .core.package import PackageReader
from .parser import PptxParser
from .renderers._render import (
    _html_comments_block,
    _html_slide_block,
    _plain_comments_block,
    _plain_slide_body,
    iter_plain,
    iter_semantic,
    iter_structural,
)
from .renderers.resources import render_resource

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
        return iter_slides(source, density=resolved, options=options)
    parsed = PptxParser().parse(source, options or ParseOptions())
    if resolved == Density.PLAIN:
        return "".join(iter_plain(parsed))
    if resolved == Density.STRUCTURAL:
        return "".join(iter_structural(parsed))
    return "".join(iter_semantic(parsed))


def iter_slides(
    source: str | Path | bytes,
    *,
    density: Density | str = Density.SEMANTIC,
    start_slide: int = 1,
    options: ParseOptions | None = None,
) -> Iterator[str]:
    """Stream rendered output: one chunk per slide, comments as a tail chunk."""
    resolved = Density.parse(density)
    parsed = PptxParser().parse(source, options or ParseOptions())
    slides = parsed.slides[start_slide - 1 :]
    if resolved == Density.PLAIN:
        first = True
        for slide in slides:
            parts: list[str] = []
            if first:
                parts.append("density=plain\n")
                first = False
            else:
                parts.append("\n")
            parts.append(f"=== Slide {slide['n']} ===\n")
            parts.append(_plain_slide_body(slide))
            yield "".join(parts)
        comments = _plain_comments_block(parsed)
        if comments:
            yield comments
        return
    smartart_nodes = {smartart["id"]: smartart for smartart in parsed.smartarts}
    semantic = resolved == Density.SEMANTIC
    first = True
    for slide in slides:
        block = _html_slide_block(slide, smartart_nodes, semantic=semantic)
        if first:
            yield f"density={resolved.value}\n{block}"
            first = False
        else:
            yield block
    comments = _html_comments_block(parsed)
    if comments:
        yield comments


def render_window(
    source: str | Path | bytes,
    *,
    slide: int,
    span: int = 1,
    density: Density | str = Density.SEMANTIC,
    options: ParseOptions | None = None,
) -> str:
    """Render a window of slides. slide is 1-based; slide=-1 selects the last slide."""
    resolved = Density.parse(density)
    parsed = PptxParser().parse(source, options or ParseOptions())
    start = len(parsed.slides) + slide if slide < 0 else slide - 1
    start = max(0, min(start, len(parsed.slides)))
    filtered = dataclasses.replace(parsed, slides=parsed.slides[start : start + span])
    if not filtered.slides:
        filtered.comments = []  # empty selection renders as an empty document
    if resolved == Density.PLAIN:
        return "".join(iter_plain(filtered))
    if resolved == Density.STRUCTURAL:
        return "".join(iter_structural(filtered))
    return "".join(iter_semantic(filtered))


def get_resource(
    source: str | Path | bytes,
    resource_type: ResourceType | str,
    resource_id: str,
    *,
    rows: str | None = None,
    columns: list[int] | None = None,
    aggregate: str | None = None,
    aggregate_column: int | None = None,
    options: ParseOptions | None = None,
) -> str | None:
    """Extract one resource by id: image/media bytes (base64), full chart/smartart/table records."""
    resolved = ResourceType.parse(resource_type)
    if resolved.is_plural:
        raise ValueError("resource_type must be singular, e.g. 'image' not 'images'")
    parsed = PptxParser().parse(source, options or ParseOptions())
    pkg: PackageReader | None = None
    if resolved in (ResourceType.IMAGE, ResourceType.MEDIA):
        pkg = PackageReader(source, options or ParseOptions())
        pkg.__enter__()
    try:
        return render_resource(
            parsed,
            pkg,
            resolved,
            resource_id,
            rows=rows,
            columns=columns,
            aggregate=aggregate,
            aggregate_column=aggregate_column,
        )
    finally:
        if pkg is not None:
            pkg.__exit__(None, None, None)


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
