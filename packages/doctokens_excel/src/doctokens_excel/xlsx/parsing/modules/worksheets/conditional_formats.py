"""Read core/x14 conditional formatting and merge explicitly linked representations."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from ....model.rules import ConditionalFormat
from ..styles.colors import SpreadsheetColors
from ..styles.index import FormatIndex
from ..styles.records import differential_style
from .rule_values import X14, XM, boolean, integer
from .sheet_types import NS_S
from .visual_rules import visual_details

_TYPES = {
    "cellIs",
    "expression",
    "colorScale",
    "dataBar",
    "iconSet",
    "top10",
    "aboveAverage",
    "containsText",
    "notContainsText",
    "beginsWith",
    "endsWith",
    "timePeriod",
    "duplicateValues",
    "uniqueValues",
    "containsBlanks",
    "notContainsBlanks",
    "containsErrors",
    "notContainsErrors",
}


def parse_conditional_formats(
    container: ET.Element,
    formats: FormatIndex | None,
    warnings: list[ParseWarning],
    locator: str,
) -> list[ConditionalFormat]:
    namespace = X14 if container.tag == f"{{{X14}}}conditionalFormatting" else NS_S
    ranges = container.findtext(f"{{{XM}}}sqref", "") if namespace == X14 else container.get("sqref", "")
    result: list[ConditionalFormat] = []
    for rule in container:
        if rule.tag in {f"{{{XM}}}sqref", f"{{{namespace}}}extLst"}:
            continue
        if rule.tag != f"{{{namespace}}}cfRule":
            result.append({"ranges": ranges, "unparsed": True})
            warnings.append(ParseWarning("CONDITIONAL_FORMAT_UNSUPPORTED", f"Unsupported rule element: {rule.tag}", locator))
            continue
        item: ConditionalFormat = {}
        if ranges.strip():
            item["ranges"] = ranges
        if kind := rule.get("type"):
            item["ruleType"] = kind
            if kind not in _TYPES:
                item["unparsed"] = True
                warnings.append(ParseWarning("CONDITIONAL_FORMAT_UNSUPPORTED", f"Unknown conditional format: {kind}", locator))
        if rule.get("priority") is not None:
            item["priority"] = integer(rule.get("priority"))
        formulas = [
            f.text or "" for f in rule.findall(f"{{{XM if namespace == X14 else NS_S}}}{'f' if namespace == X14 else 'formula'}")
        ]
        if formulas:
            item["formulas"] = formulas
        identifier = (
            rule.get("id")
            if namespace == X14
            else rule.findtext(
                f"{{{NS_S}}}extLst/{{{NS_S}}}ext/{{{X14}}}id",
                "",
            )
        )
        if identifier:
            item["extensionId"] = identifier.casefold()
        if rule.get("dxfId") is not None:
            index = integer(rule.get("dxfId"), -1)
            if formats is not None and (style := formats.differential_style(index)):
                item["dxfStyle"] = style
        inline = rule.find(f"{{{X14}}}dxf")
        if inline is not None:
            style = differential_style(
                inline, formats.colors if formats is not None else SpreadsheetColors(), warnings=warnings, locator=locator
            )
            if style:
                item["dxfStyle"] = style
        for key in ("operator", "text", "timePeriod"):
            if (value := rule.get(key)) is not None:
                item[key] = value
        for key in ("rank", "stdDev"):
            if rule.get(key) is not None:
                item[key] = integer(rule.get(key))  # type: ignore[literal-required]
        for key in ("stopIfTrue", "percent", "bottom", "aboveAverage", "equalAverage"):
            if rule.get(key) is not None:
                item[key] = boolean(rule.get(key), key == "aboveAverage", warnings=warnings, locator=locator)  # type: ignore[literal-required]
        if (
            detail := visual_details(
                rule, formats.colors if formats is not None else SpreadsheetColors(), warnings=warnings, locator=locator
            )
        ) is not None:
            item["formatKind"], item["formatDetails"] = detail
        result.append(item)
    return result


def merge_conditional_formats(
    primary: list[ConditionalFormat],
    extensions: list[ConditionalFormat],
) -> list[ConditionalFormat]:
    by_id = {item["extensionId"]: item for item in primary if item.get("extensionId")}
    result = list(primary)
    for extension in extensions:
        target = by_id.get(extension.get("extensionId", ""))
        if target is None:
            result.append(extension)
            continue
        if "formatDetails" in extension:
            target["formatDetails"] = {**target.get("formatDetails", {}), **extension["formatDetails"]}
        for key, value in extension.items():
            if key != "formatDetails":
                target[key] = value  # type: ignore[literal-required]
    return result
