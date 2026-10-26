"""Reuse worksheet preflights to plan the shared strings needed by previews."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.models import RelationshipRecord
from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.contracts.models import ParseWarning

from ..model.workbook import SheetInfo
from .modules.styles.index import FormatIndex
from .modules.worksheets.preview import PreparedPreview, preview_state
from .modules.worksheets.sheet_types import SheetParseFlags
from .plan import XlsxParsePlan


def read_sheet_relationships(
    package: PackageReader, sheets: list[SheetInfo], warnings: list[ParseWarning]
) -> dict[str, list[RelationshipRecord]]:
    records: dict[str, list[RelationshipRecord]] = {}
    for sheet in sheets:
        if sheet.get("kind") == "chartsheet":
            continue
        part = sheet["part"]
        try:
            records[part] = list(package.read_relationships_for_part(part))
        except (ET.ParseError, KeyError, ValueError) as exc:
            warnings.append(ParseWarning("SHEET_RELS_INVALID", f"Invalid worksheet relationships: {exc}", part))
            records[part] = []
    return records


def prepare_previews(
    package: PackageReader,
    sheets: list[SheetInfo],
    plan: XlsxParsePlan,
    formats: FormatIndex,
    relationships: dict[str, list[RelationshipRecord]],
) -> tuple[dict[str, PreparedPreview], set[int] | None]:
    if not plan.preview:
        return {}, None
    prepared: dict[str, PreparedPreview] = {}
    indices: set[int] | None = set()
    flags = SheetParseFlags.from_plan(plan)
    for sheet in sheets:
        if sheet.get("kind") == "chartsheet":
            continue
        part = sheet["part"]
        state = preview_state(package, part, formats, flags, relationships[part], plan.density)
        prepared[part] = PreparedPreview(state)
        if state is None or state.shared_string_indices is None:
            indices = None
        elif indices is not None:
            indices.update(state.shared_string_indices)
    return prepared, indices
