"""Public workbook orientation without loading shared strings or cells."""

from __future__ import annotations

from pathlib import Path

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.package import PackageReader

from .models import ParseOptions
from .parsing.modules.workbook.metadata import _parse_workbook_xml


def inspect_xlsx(source: str | Path | bytes, *, options: ParseOptions | None = None) -> dict[str, object]:
    """Read the workbook index only; cell/resource counts remain unknown."""
    selected = options or ParseOptions()
    limits = PackageLimits(selected.max_zip_entries, selected.max_entry_uncompressed_bytes, selected.max_total_uncompressed_bytes)
    with PackageReader(source, limits) as package:
        package.validate("xl/workbook.xml")
        date_1904, sheets, names, links = _parse_workbook_xml(package, include_defined_names=True, include_external_links=True)
    return {
        "format": "xlsx",
        "scope": "workbook-index",
        "sheet_count": len(sheets),
        "sheets": [{"name": s["name"], "kind": s["kind"], "visibility": s.get("state", "visible")} for s in sheets],
        "date_1904": date_1904,
        "defined_names": names,
        "external_links": links,
    }
