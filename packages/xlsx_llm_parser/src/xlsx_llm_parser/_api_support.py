"""Public XLSX parsing and explicit read-session API."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from ooxml_llm_core.models import Density, ParseResult

from ._resources import _resource_descriptors
from .models import ParsedWorkbook

Source = str | Path | bytes
_DENSITIES = {"plain", "structural", "semantic"}


def _density(value: str) -> str:
    if value not in _DENSITIES:
        raise ValueError(f"density must be one of: {', '.join(sorted(_DENSITIES))}")
    return value


def _result(
    workbook: ParsedWorkbook,
    text: str,
    density: str,
    selection: dict[str, object],
    *,
    syntax_version: str | None = None,
    media_type: str | None = None,
) -> ParseResult:
    resolved_syntax, resolved_media_type = _output_metadata(density)
    return ParseResult(
        text,
        cast(Density, density),
        selection,
        workbook["report"],
        _resource_descriptors(workbook),
        syntax_version or resolved_syntax,
        media_type or resolved_media_type,
    )


def _output_metadata(density: str) -> tuple[str, str]:
    if density == "plain":
        return "doctokens-plain/1.0", "text/plain"
    return "doctokens-xml/1.0", "application/xml"
