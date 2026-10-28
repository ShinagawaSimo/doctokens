"""Traverse retained DOCX block structure, including text-box stories."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from . import Block, InlineContainer, ParsedDocument, Run


def iter_runs(runs: Iterable[Run]) -> Iterator[Run]:
    for run in runs:
        yield run
        if ruby := run.get("ruby"):
            yield from iter_runs(ruby["baseRuns"])


def textbox_blocks(container: InlineContainer) -> Iterator[Block]:
    for run in iter_runs(container.get("runs", [])):
        for item in run.get("objects", []):
            yield from item.get("blocks", [])


def iter_blocks(blocks: Iterable[Block]) -> Iterator[Block]:
    for block in blocks:
        yield block
        if block["type"] == "table":
            for row in block["rows"]:
                for cell in row["cells"]:
                    yield from iter_blocks(cell["blocks"])
        else:
            yield from iter_blocks(textbox_blocks(block))


def document_blocks(document: ParsedDocument) -> Iterator[Block]:
    yield from iter_blocks(document.blocks)
    for group in (document.headers, document.footers, document.footnotes, document.endnotes, document.comments):
        for content in group:
            yield from iter_blocks(textbox_blocks(content))
