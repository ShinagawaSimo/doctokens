"""Public XLSX parsing and explicit read-session API."""

from __future__ import annotations

from typing import cast

from doctokens_core.contracts.models import Density, ParseResult

from ..model.workbook import ParsedWorkbook
from .resources import _resource_descriptors

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
        text=text,
        density=cast(Density, density),
        selection=selection,
        report=workbook["report"],
        resources=_resource_descriptors(workbook),
        syntax_version=syntax_version or resolved_syntax,
        media_type=media_type or resolved_media_type,
    )


def _output_metadata(density: str) -> tuple[str, str]:
    if density == "plain":
        return "doctokens-plain/1.0", "text/plain"
    return "doctokens-xml/1.0", "application/xml"
