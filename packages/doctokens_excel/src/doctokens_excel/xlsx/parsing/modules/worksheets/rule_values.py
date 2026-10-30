"""Namespace and scalar decoding for saved worksheet rule declarations."""

from __future__ import annotations

from doctokens_core.contracts.models import ParseWarning

X14 = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
XM = "http://schemas.microsoft.com/office/excel/2006/main"


def integer(value: str | None, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def boolean(
    value: str | None,
    default: bool = False,
    *,
    warnings: list[ParseWarning] | None = None,
    locator: str = "",
) -> bool:
    if value is None:
        return default
    if value in {"1", "true"}:
        return True
    if value in {"0", "false"}:
        return False
    if warnings is not None:
        warnings.append(ParseWarning("RULE_BOOLEAN_INVALID", f"Invalid rule boolean: {value!r}", locator))
    return default
