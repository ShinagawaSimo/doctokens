"""One strict input contract shared by MCP and direct calls."""

from __future__ import annotations

from typing import Literal

from doctokens_core.models import Density
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

_DENSITY_HELP = (
    "Use plain for text-only questions, structural for coordinates/resource links and explicit relationships, "
    "semantic when emphasis, color or review context affects the answer."
)


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class BaseOptions(Arguments):
    enable_ocr: bool = False


class DocxOptions(BaseOptions):
    revision_mode: Literal["final", "original", "review"] | None = None
    preserve_empty_paragraphs: bool | None = None
    include_runs: bool | None = None
    include_raw_hints: bool | None = None


class XlsxOptions(BaseOptions):
    locale: str | None = Field(default=None, min_length=1)
    enable_ocr: Literal[False] = False


class PptxOptions(BaseOptions):
    pass


class DocumentOptions(DocxOptions):
    """Options for tools accepting all three formats; applicability is checked by suffix."""

    locale: str | None = Field(default=None, min_length=1)


class BaseSourceArgs(Arguments):
    path: str | None = Field(default=None, min_length=1, description="Local Office file within an allowed root.")
    document_id: str | None = Field(default=None, min_length=1, description="Pinned snapshot ID returned by a previous call.")
    options: BaseOptions = Field(default_factory=BaseOptions)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if (self.path is None) == (self.document_id is None):
            raise ValueError("provide exactly one of path and document_id")
        if self.document_id is not None and self.options.model_fields_set:
            raise ValueError("options are pinned by document_id; use path to change them")
        return self


class SourceArgs(BaseSourceArgs):
    options: DocumentOptions = Field(
        default_factory=DocumentOptions,
        description="DOCX: revision_mode, preserve_empty_paragraphs, include_runs, include_raw_hints, enable_ocr; "
        "XLSX: locale; PPTX: enable_ocr. OCR needs a host provider. document_id pins options; use path to change them.",
    )


class InspectArgs(SourceArgs):
    full_parse: bool = Field(
        default=False,
        description="Explicitly return the full parse report, source revision and diagnostics. Default returns navigation only.",
    )


class ReadArgs(BaseSourceArgs):
    density: Density = Field(default="structural", description=_DENSITY_HELP)
    whole_document: bool = Field(
        default=False, description="Explicitly read all content; large results are retrieved separately."
    )


class DocxReadArgs(ReadArgs):
    options: DocxOptions = Field(default_factory=DocxOptions)
    page_start: int = Field(default=1, ge=1)
    page_end: int | None = Field(default=None, ge=1, description="Inclusive end; defaults to start + 2.")


class PptxReadArgs(ReadArgs):
    options: PptxOptions = Field(default_factory=PptxOptions)
    slide_start: int = Field(default=1, ge=1)
    slide_end: int | None = Field(default=None, ge=1)


class XlsxReadArgs(BaseSourceArgs):
    options: XlsxOptions = Field(default_factory=XlsxOptions)
    density: Density = Field(default="structural", description=_DENSITY_HELP)
    sheet: str | None = Field(default=None, min_length=1, description="Exact sheet name; defaults to the first worksheet.")
    range_spec: str | None = Field(
        default=None,
        description=(
            "Inclusive rectangle A1:H20, whole rows 10:20, or one cell A1; requires sheet. "
            "Explicit ranges are exact. Omit to preview 500 emitted cells, finishing the last row. "
            "Use selection.windows next_row/next_cell to choose the next explicit range."
        ),
    )

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        if self.range_spec is not None and self.sheet is None:
            raise ValueError("range_spec requires sheet")
        return self


class BinaryArgs(SourceArgs):
    kind: Literal["image", "media"]
    resource_id: str = Field(min_length=1)


class ResourceArgs(BaseSourceArgs):
    resource_id: str = Field(min_length=1)


Aggregate = Literal["sum", "count", "avg", "min", "max"]


class DocxResourceArgs(ResourceArgs):
    options: DocxOptions = Field(default_factory=DocxOptions)
    kind: Literal["table", "chart", "smartart"]
    rows: str | None = None
    columns: list[str] | None = None
    aggregate: Aggregate | None = None
    aggregate_column: str | None = None


class PptxResourceArgs(ResourceArgs):
    options: PptxOptions = Field(default_factory=PptxOptions)
    kind: Literal["table", "chart", "smartart"]
    rows: str | None = None
    columns: list[int] | None = None
    aggregate: Aggregate | None = None
    aggregate_column: int | None = Field(default=None, ge=0)


class XlsxResourceArgs(ResourceArgs):
    options: XlsxOptions = Field(default_factory=XlsxOptions)
    kind: Literal["chart", "pivot_table"]


class FindArgs(BaseSourceArgs):
    options: XlsxOptions = Field(default_factory=XlsxOptions)
    query: str
    sheets: list[str] | None = None
    kind: Literal["value", "formula", "comment", "hyperlink", "definedName"] | None = None
    limit: int = Field(default=50, gt=0)


class TextFindArgs(SourceArgs):
    query: str = Field(
        min_length=1, max_length=4000, description="Literal text, not a regular expression; never joins unrelated paragraphs."
    )
    case_sensitive: bool = True
    offset: int = Field(default=0, ge=0, description="Number of matching paragraphs/cells to skip; use the returned next_offset.")
    limit: int = Field(default=20, ge=1, le=200)
    context_before: int = Field(default=80, ge=0, le=4000, description="Characters before the first match in its paragraph/cell.")
    context_after: int = Field(default=80, ge=0, le=4000, description="Characters after the first match in its paragraph/cell.")
    include_headers_footers: bool = Field(
        default=False, description="DOCX only; search headers and footers once by source, without repeating them per page."
    )
    sheets: list[str] | None = Field(default=None, description="XLSX only: exact sheet names; omitted searches all sheets.")


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


class QueryArgs(BaseSourceArgs):
    options: XlsxOptions = Field(default_factory=XlsxOptions)
    table_id: str | None = Field(default=None, min_length=1)
    sheet: str | None = Field(default=None, min_length=1)
    range_spec: str | None = Field(default=None, min_length=1)
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
    offset: int = Field(
        default=0, ge=0, description="Continue at the previous next_offset; zero deliberately rereads the beginning."
    )
    length: int | None = Field(default=None, gt=0)


class RuntimeInfoArgs(Arguments):
    pass
