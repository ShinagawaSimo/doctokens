"""Text traversal over selected DOCX stories, without serialized markup."""

from __future__ import annotations

from collections.abc import Iterator

from doctokens_core.text.search import Locator, TextUnit

from ..model import Block, InlineContainer, ParsedDocument


def text_units(document: ParsedDocument, *, include_headers_footers: bool = False) -> Iterator[TextUnit]:
    references: dict[tuple[str, str], Locator] = {}
    for block in document.blocks:
        yield from _block(block, {"source": "body"}, references)
    groups = [("footnote", document.footnotes), ("endnote", document.endnotes), ("comment", document.comments)]
    if include_headers_footers:
        groups.extend((("header", document.headers), ("footer", document.footers)))
    for source, items in groups:
        for item in items:
            identity = item.get("id") or item["loc"]
            locator: Locator = {**references.get((source, identity), {}), "source": source, "item_id": identity}
            for index, unit in enumerate(item.get("searchUnits", []), 1):
                position = {**locator, "paragraph": index}
                for key in ("table", "row", "column"):
                    if key in unit:
                        position[key] = unit[key]
                group = (
                    f"{source}:{identity}:{unit.get('table')}:{unit.get('row')}:{unit.get('column')}" if "table" in unit else ""
                )
                yield TextUnit(unit.get("text", ""), position, group)
            yield from _objects(item, locator, references)


def _block(block: Block, inherited: Locator, references: dict[tuple[str, str], Locator], group: str = "") -> Iterator[TextUnit]:
    locator: Locator = dict(inherited)
    if inherited.get("source") != "textbox":
        locator["page_start"] = block["page"]
        locator.pop("page_end", None)
        if block.get("pageEnd", block["page"]) != block["page"]:
            locator["page_end"] = block["pageEnd"]
    if block["type"] == "table":
        for row in block["rows"]:
            for cell in row["cells"]:
                cell_locator = {
                    **locator,
                    "table_id": block["tableId"],
                    "row": cell["rowIndex"] + 1,
                    "column": cell["colIndex"] + 1,
                }
                key = f"{block['tableId']}:{cell['rowIndex']}:{cell['colIndex']}"
                for child in cell["blocks"]:
                    yield from _block(child, cell_locator, references, key)
        return
    locator = {**locator, "block_id": block["id"]}
    yield TextUnit(block["text"], locator, group)
    yield from _objects(block, locator, references)


def _objects(container: InlineContainer, locator: Locator, references: dict[tuple[str, str], Locator]) -> Iterator[TextUnit]:
    for run in container.get("runs", []):
        for item in run.get("objects", []):
            kind = item["type"]
            if kind in {"footnoteRef", "endnoteRef", "commentRef"} and item.get("id"):
                references.setdefault((kind.removesuffix("Ref"), str(item["id"])), locator)
            if kind == "textbox":
                nested: Locator = {**locator, "source": "textbox"}
                if locator.get("source") not in {"body", "textbox"}:
                    nested["story_source"] = locator["source"]
                if item.get("id"):
                    nested["textbox_id"] = str(item["id"])
                for block in item.get("blocks", []):
                    yield from _block(block, nested, references)
                if "blocks" not in item:
                    for index, text in enumerate(item.get("text", "").splitlines(), 1):
                        yield TextUnit(text, {**nested, "paragraph": index})
