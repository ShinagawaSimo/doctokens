"""Discoverable operations and their generated input schemas."""

from __future__ import annotations

from . import schemas as s
from .models import ToolDefinition

OPERATIONS: dict[str, tuple[type[s.Arguments], str]] = {
    "inspect_document": (s.SourceArgs, "Inspect saved-page hints, slides, or a lightweight workbook sheet index."),
    "read_docx": (
        s.DocxReadArgs,
        "Read a saved-page hint interval, default first 3 pages. These are not newly computed Word layout pages.",
    ),
    "read_pptx": (s.PptxReadArgs, "Read a slide interval, default first 3 slides, including saved notes and supported comments."),
    "read_xlsx": (
        s.XlsxReadArgs,
        "Read a sheet/range; no selection returns the sheet index. Saved formulas are not recalculated.",
    ),
    "list_document_resources": (
        s.SourceArgs,
        "List images and objects with supported binary/render operations. Loads a full read session.",
    ),
    "read_resource": (s.BinaryArgs, "Read embedded image/media bytes. External targets are never downloaded."),
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


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(name, description, model.model_json_schema(), dict(OUTPUT_SCHEMA))
        for name, (model, description) in OPERATIONS.items()
    ]
