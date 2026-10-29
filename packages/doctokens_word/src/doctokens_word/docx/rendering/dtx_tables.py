"""DTX table rows and logical cell positions with controls and review marks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from xml.etree import ElementTree as ET

from doctokens_core.output.xml import append

from ..model import OcrResultRecord, TableRow
from .dtx_content import _append_controls
from .dtx_runs import review_parent


def append_rows(
    parent: ET.Element,
    rows: Sequence[TableRow],
    density: str,
    ocr_results: dict[str, OcrResultRecord],
    append_cell: Callable[[ET.Element, object, str, dict[str, OcrResultRecord]], None],
) -> None:
    for row in rows:
        container = review_parent(_append_controls(parent, row.get("contentControls", []), density), row, density)
        node = append(
            container,
            "tr",
            header=True if row.get("isHeader") else None,
            grid_before=row.get("gridBefore"),
            grid_after=row.get("gridAfter"),
        )
        for cell in row["cells"]:
            container = review_parent(_append_controls(node, cell.get("contentControls", []), density), cell, density)
            child = append(
                container,
                "th" if row.get("isHeader") else "td",
                colspan=cell["colSpan"] if cell["colSpan"] != 1 else None,
                rowspan=cell["rowSpan"] if cell["rowSpan"] != 1 else None,
                v_merge=cell.get("vMerge"),
                background=cell.get("background") if density == "semantic" else None,
            )
            append_cell(child, cell, density, ocr_results)
