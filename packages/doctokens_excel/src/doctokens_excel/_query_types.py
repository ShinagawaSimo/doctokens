"""query types."""

from __future__ import annotations

from typing import TypedDict


class WhereCondition(TypedDict, total=False):
    column: str
    op: str
    value: object


AggregateSpec = TypedDict(
    "AggregateSpec",
    {"op": str, "column": str, "as": str},
    total=False,
)


class OrderSpec(TypedDict, total=False):
    column: str
    direction: str


class QueryColumn(TypedDict):
    key: str
    label: str
    col: int
