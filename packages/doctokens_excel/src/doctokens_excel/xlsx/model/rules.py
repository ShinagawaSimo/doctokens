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
        "color": str,
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
    showInputMessage: bool
    showErrorMessage: bool
    promptTitle: str
    prompt: str
    errorTitle: str
    error: str
    unparsed: bool


class ConditionalStyle(TypedDict, total=False):
    bold: bool
    italic: bool
    underline: bool
    strike: bool
    color: str
    fill: str
    number_format: str


class FormatThreshold(TypedDict, total=False):
    type: str
    val: str
    gte: str
    color: str


class FormatIcon(TypedDict, total=False):
    iconSet: str
    iconId: str


class VisualDetails(TypedDict, total=False):
    stops: list[FormatThreshold]
    thresholds: list[FormatThreshold]
    icons: list[FormatIcon]
    color: str
    negativeFillColor: str
    showValue: str
    reverse: str
    iconSet: str


class ConditionalFormat(TypedDict, total=False):
    ranges: str
    priority: int
    ruleType: str
    formulas: list[str]
    stopIfTrue: bool
    operator: str
    text: str
    rank: int
    percent: bool
    formatKind: str
    formatDetails: VisualDetails
    dxfStyle: ConditionalStyle
    extensionId: str
    unparsed: bool
    aboveAverage: bool
    bottom: bool
    equalAverage: bool
    stdDev: int
    timePeriod: str
