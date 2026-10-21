"""Discoverable operations and their generated input schemas."""

from __future__ import annotations

from . import schemas as s
from .config import RuntimeConfig
from .contracts import input_schema, result_limits
from .models import ToolDefinition

OPERATIONS: dict[str, tuple[type[s.Arguments], str]] = {
    "get_runtime_info": (s.RuntimeInfoArgs, "Inspect active allowed roots, result budgets, OCR availability and cache usage."),
    "inspect_document": (
        s.InspectArgs,
        "Discover navigation only when needed; full_parse=true explicitly requests the full report.",
    ),
    "read_docx": (
        s.DocxReadArgs,
        "Read a saved-page hint interval, default first 3 pages. These are not newly computed Word layout pages.",
    ),
    "read_pptx": (s.PptxReadArgs, "Read a slide interval, default first 3 slides, including saved notes and supported comments."),
    "read_xlsx": (
        s.XlsxReadArgs,
        "Read one sheet. Default: first worksheet, 500 cells finishing the last row, plus the sheet index. "
        "Explicit A1:H20, 10:20, or A1 ranges are exact. Window metadata gives returned_range and next_row. "
        "Saved formulas are not recalculated; XLSX has no whole_document parameter.",
    ),
    "list_document_resources": (
        s.SourceArgs,
        "List images and objects with supported binary/render operations. Loads a full read session.",
    ),
    "read_resource": (
        s.BinaryArgs,
        "Read original embedded image/media. MCP inlines supported images within the size cap; otherwise returns a resource URI. "
        "External targets are never downloaded.",
    ),
    "render_docx_resource": (
        s.DocxResourceArgs,
        "Read full chart/SmartArt data or table rows/columns/aggregation; columns use header names.",
    ),
    "render_pptx_resource": (s.PptxResourceArgs, "Read chart/SmartArt/table details; table columns use zero-based indices."),
    "render_xlsx_resource": (s.XlsxResourceArgs, "Read chart details or the supported pivot-table summary."),
    "find_xlsx_cells": (
        s.FindArgs,
        "Search saved cell values, formulas, comments, hyperlinks, or defined names; literal case-sensitive matching.",
    ),
    "query_xlsx_data": (
        s.QueryArgs,
        "Experimental saved-data query: projection, filtering, grouping, aggregation and sorting. Not SQL or formula evaluation.",
    ),
    "read_result": (
        s.ResultArgs,
        "Retrieve text characters or binary bytes from an immutable saved result. Fragments are not standalone XML.",
    ),
    "release_document": (
        s.SourceArgs,
        "Release a snapshot, session and associated saved results. Paths may be read again afterwards.",
    ),
}

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["ok", "data"],
    "properties": {
        "ok": {"type": "boolean"},
        "data": {"type": "object"},
        "error": {"type": "object"},
        "attachments": {"type": "array"},
    },
}


def definitions(config: RuntimeConfig) -> list[ToolDefinition]:
    tools = []
    for name, (model, description) in OPERATIONS.items():
        if issubclass(model, s.BaseSourceArgs):
            description += (
                " Provide exactly one of path/document_id. With document_id options are pinned; omit options or use {}."
            )
        if name == "query_xlsx_data":
            description += (
                " Provide table_id OR all of sheet + range_spec + header_row. Example: "
                '{"path":"book.xlsx","sheet":"Data","range_spec":"A1:C20","header_row":1}. '
                "Headers are never guessed."
            )
        if name == "read_result":
            limits = result_limits(config)
            description += " Current host limits: " + ", ".join(f"{key}={value}" for key, value in limits.items()) + "."
        if name.startswith("render_"):
            description += " Returns object data, not a visual image."
        tools.append(ToolDefinition(name, description, input_schema(model, config), dict(OUTPUT_SCHEMA)))
    return tools
