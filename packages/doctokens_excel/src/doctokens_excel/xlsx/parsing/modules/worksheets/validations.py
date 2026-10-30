"""Standard and x14 data-validation constraints, prompts and error text."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from ....model.rules import DataValidation
from ..workbook.string_text import decode_xstring
from .rule_values import X14, XM, boolean
from .sheet_types import NS_S

_TYPES = {"none", "whole", "decimal", "list", "date", "time", "textLength", "custom"}
_OPERATORS = {"between", "notBetween", "equal", "notEqual", "lessThan", "lessThanOrEqual", "greaterThan", "greaterThanOrEqual"}


def parse_validations(container: ET.Element, warnings: list[ParseWarning], locator: str) -> list[DataValidation]:
    namespace = X14 if container.tag == f"{{{X14}}}dataValidations" else NS_S
    disabled = boolean(container.get("disablePrompts"), warnings=warnings, locator=locator)
    result: list[DataValidation] = []
    for element in container:
        if element.tag != f"{{{namespace}}}dataValidation":
            if element.tag != f"{{{namespace}}}extLst":
                result.append({"unparsed": True})
                warnings.append(
                    ParseWarning("DATA_VALIDATION_UNSUPPORTED", f"Unsupported validation element: {element.tag}", locator)
                )
            continue
        ranges = element.findtext(f"{{{XM}}}sqref", "") if namespace == X14 else element.get("sqref", "")
        kind = element.get("type", "none")
        item: DataValidation = {"ranges": ranges, "type": kind}
        if kind not in _TYPES or not ranges.strip():
            item["unparsed"] = True
            warnings.append(
                ParseWarning("DATA_VALIDATION_UNSUPPORTED", f"Unreadable validation type/range: {kind!r}, {ranges!r}", locator)
            )
        if kind in {"whole", "decimal", "date", "time", "textLength"}:
            operator = element.get("operator", "between")
            item["operator"] = operator
            if operator not in _OPERATORS:
                item["unparsed"] = True
                warnings.append(ParseWarning("DATA_VALIDATION_UNSUPPORTED", f"Unknown validation operator: {operator}", locator))
        for key in ("formula1", "formula2"):
            node = element.find(f"{{{namespace}}}{key}")
            if node is not None:
                value = node.findtext(f"{{{XM}}}f", "") if namespace == X14 else node.text or ""
                item[key] = value
        for key in ("allowBlank", "showDropDown", "showInputMessage", "showErrorMessage"):
            item[key] = boolean(element.get(key), warnings=warnings, locator=locator)  # type: ignore[literal-required]
        if disabled:
            item["showInputMessage"] = False
        for key in ("promptTitle", "prompt", "errorTitle", "error"):
            if (label := element.get(key)) is not None:
                item[key] = decode_xstring(label, warn=lambda c, m: warnings.append(ParseWarning(c, m, locator)))  # type: ignore[literal-required]
        for key, default in (("errorStyle", "stop"), ("imeMode", "noControl")):
            if (value := element.get(key, default)) != default:
                item[key] = value  # type: ignore[literal-required]
        if kind not in {"none"} and not item.get("formula1"):
            item["unparsed"] = True
            warnings.append(
                ParseWarning("DATA_VALIDATION_FORMULA_MISSING", "Validation has no saved constraint formula", locator)
            )
        if item.get("operator") in {"between", "notBetween"} and not item.get("formula2"):
            item["unparsed"] = True
            warnings.append(
                ParseWarning("DATA_VALIDATION_FORMULA_MISSING", "Range validation has no second saved formula", locator)
            )
        result.append(item)
    return result
