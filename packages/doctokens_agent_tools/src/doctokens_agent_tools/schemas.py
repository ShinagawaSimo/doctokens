"""One strict input contract shared by MCP and direct calls."""

from __future__ import annotations

from typing import Literal

from ooxml_llm_core.models import Density
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DocumentOptions(Arguments):
    revision_mode: Literal["final", "original", "review"] | None = None
    preserve_empty_paragraphs: bool | None = None
    include_runs: bool | None = None
    include_raw_hints: bool | None = None
    locale: str | None = Field(default=None, min_length=1)
    enable_ocr: bool = False


class SourceArgs(Arguments):
    path: str | None = Field(default=None, min_length=1, description="Local Office file within an allowed root.")
    document_id: str | None = Field(default=None, min_length=1, description="Pinned snapshot ID returned by a previous call.")
    options: DocumentOptions = Field(default_factory=DocumentOptions)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if (self.path is None) == (self.document_id is None):
            raise ValueError("provide exactly one of path and document_id")
        if self.document_id is not None and self.options.model_fields_set:
            raise ValueError("options are pinned by document_id; use path to change them")
        return self


class ReadArgs(SourceArgs):
    density: Density = "structural"
    whole_document: bool = Field(
        default=False, description="Explicitly read all content; large results are retrieved separately."
    )


class DocxReadArgs(ReadArgs):
    page_start: int = Field(default=1, ge=1)
    page_end: int | None = Field(default=None, ge=1, description="Inclusive end; defaults to start + 2.")


class PptxReadArgs(ReadArgs):
    slide_start: int = Field(default=1, ge=1)
    slide_end: int | None = Field(default=None, ge=1)


class XlsxReadArgs(ReadArgs):
    sheet: str | None = Field(default=None, min_length=1)
    range_spec: str | None = Field(default=None, description="Inclusive A1:B2 range; one cell is A1:A1.")

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        if self.range_spec is not None and self.sheet is None:
            raise ValueError("range_spec requires sheet")
        if self.whole_document and (self.sheet is not None or self.range_spec is not None):
            raise ValueError("whole_document cannot be combined with sheet or range_spec")
        return self


class BinaryArgs(SourceArgs):
    kind: Literal["image", "media"]
    resource_id: str = Field(min_length=1)


class ResourceArgs(SourceArgs):
    resource_id: str = Field(min_length=1)


Aggregate = Literal["sum", "count", "avg", "min", "max"]


class DocxResourceArgs(ResourceArgs):
    kind: Literal["table", "chart", "smartart"]
    rows: str | None = None
    columns: list[str] | None = None
    aggregate: Aggregate | None = None
    aggregate_column: str | None = None


class PptxResourceArgs(ResourceArgs):
    kind: Literal["table", "chart", "smartart"]
    rows: str | None = None
    columns: list[int] | None = None
    aggregate: Aggregate | None = None
    aggregate_column: int | None = Field(default=None, ge=0)


class XlsxResourceArgs(ResourceArgs):
    kind: Literal["chart", "pivot_table"]


class FindArgs(SourceArgs):
    query: str
    sheets: list[str] | None = None
    kind: Literal["value", "formula", "comment", "hyperlink", "definedName"] | None = None
    limit: int = Field(default=50, gt=0)


class Where(Arguments):
    column: str = Field(min_length=1)
    op: Literal["eq", "contains", "gt", "lt"] = "eq"
    value: str | int | float | bool | None = None


class AggregateArgs(Arguments):
    op: Aggregate = "sum"
    column: str = Field(min_length=1)
    alias: str | None = Field(default=None, alias="as")


class Order(Arguments):
    column: str = Field(min_length=1)
    direction: Literal["asc", "desc"] = "asc"


class QueryArgs(SourceArgs):
    table_id: str | None = None
    sheet: str | None = None
    range_spec: str | None = None
    header_row: int | None = Field(default=None, ge=1)
    select: list[str] | None = None
    where: list[Where] | None = None
    group_by: list[str] | None = Field(
        default=None, description="Grouping runs only when both group_by and aggregates are nonempty."
    )
    aggregates: list[AggregateArgs] | None = Field(
        default=None, description="Requires nonempty group_by to aggregate, as in the parser API."
    )
    order_by: list[Order] | None = None
    limit: int | None = Field(default=100, gt=0)

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        if self.table_id is None and (self.sheet is None or self.range_spec is None or self.header_row is None):
            raise ValueError("provide table_id or sheet + range_spec + header_row")
        return self


class ResultArgs(Arguments):
    result_id: str = Field(min_length=1)
    offset: int = Field(default=0, ge=0)
    length: int | None = Field(default=None, gt=0)
