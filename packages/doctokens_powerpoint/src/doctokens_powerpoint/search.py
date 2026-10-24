"""Text traversal in slide/source order, with explicit notes/comment origins."""

from __future__ import annotations

from collections.abc import Iterator

from doctokens_core.text_search import Locator, TextUnit

from .core.models import ParsedPresentation


def text_units(presentation: ParsedPresentation) -> Iterator[TextUnit]:
    comments = {item.get("id"): item for item in presentation.comments}
    for slide in presentation.slides:
        for shape in slide["shapes"]:
            locator: Locator = {"slide_start": slide["n"], "source": "body", "shape_id": shape["id"]}
            if shape.get("type") == "table":
                for row, cells in enumerate(shape.get("rows", []), 1):
                    for column, value in enumerate(cells, 1):
                        details = shape.get("tableCells", [])
                        cell = details[row - 1][column - 1] if row <= len(details) and column <= len(details[row - 1]) else {}
                        if cell.get("hMerge") or cell.get("vMerge"):
                            continue
                        cell_locator = {**locator, "row": row, "column": column}
                        if shape.get("tableId"):
                            cell_locator["table_id"] = shape["tableId"]
                        for text in cell.get("searchParagraphs", value.splitlines()):
                            yield TextUnit(text, cell_locator, f"{slide['n']}:{shape['id']}:{row}:{column}")
            elif shape.get("paragraphs"):
                for index, paragraph in enumerate(shape["paragraphs"], 1):
                    runs = paragraph.get("runs", [])
                    if runs and (paragraph.get("bullet") or paragraph.get("numberType")):
                        # shape_runs inserts exactly one synthetic list-prefix
                        # run before the source runs. It is navigation markup,
                        # not a character sequence from the paragraph itself.
                        value = "".join(run.get("text", "") for run in runs[1:])
                    else:
                        value = paragraph.get("text", "")
                    yield TextUnit(value, {**locator, "paragraph": index})
            elif shape.get("text"):
                yield TextUnit(shape["text"], locator)
        for index, text in enumerate((slide.get("notes") or "").splitlines(), 1):
            yield TextUnit(text, {"slide_start": slide["n"], "source": "notes", "paragraph": index})
        for reference in slide.get("commentRefs", []):
            item = comments.get(reference.get("id"))
            if item is not None:
                for index, text in enumerate(item.get("text", "").splitlines(), 1):
                    yield TextUnit(
                        text, {"slide_start": slide["n"], "source": "comment", "item_id": item.get("id", ""), "paragraph": index}
                    )
