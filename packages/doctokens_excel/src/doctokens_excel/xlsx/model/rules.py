"""Worksheet filter, validation and conditional-format declarations."""

from typing import TypedDict

FilterColumn = TypedDict(
    "FilterColumn",
    {
        "col": int,
        "type": str,
        "values": list[str],
        "blank": bool,
        "calendarType": str,
        "operator": str,
        "value": str,
        "value2": str,
        "and": bool,
        "top": bool,
        "percent": bool,
        "rank": str,
        "filterValue": str,
        "dxfId": int,
        "cellColor": bool,
        "iconSet": str,
        "iconId": int,
        "dateGroup": list[dict[str, str]],
    },
    total=False,
)


class DataValidation(TypedDict, total=False):
    ranges: str
    type: str
    formula1: str
    allowBlank: bool
    formula2: str
    operator: str
    errorStyle: str
    imeMode: str
    showDropDown: bool
    showInputMessage: bool
    showErrorMessage: bool
    promptTitle: str
    prompt: str
    errorTitle: str
    error: str
    unparsed: bool


class ConditionalFormat(TypedDict, total=False):
    ranges: str
    priority: int
    ruleType: str
    formulas: list[str]
    dxfId: int
    stopIfTrue: bool
    operator: str
    text: str
    rank: int
    percent: bool
    formatKind: str
    formatDetails: dict[str, object]
    dxfStyle: str
    extensionId: str
    unparsed: bool
    aboveAverage: bool
    bottom: bool
    equalAverage: bool
    stdDev: int
    timePeriod: str
