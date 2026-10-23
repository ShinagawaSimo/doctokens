"""Format-aware tool operations using only public parser APIs."""

from __future__ import annotations

import json
import mimetypes
from functools import partial
from typing import Any, cast

from docx_llm_parser import DocxReadSession
from ooxml_llm_core.models import ParseResult
from ooxml_llm_core.text_search import TextSearchOptions
from pptx_llm_parser import PptxReadSession
from xlsx_llm_parser import (
    AggregateSpec,
    OrderSpec,
    WhereCondition,
    XlsxReadSession,
    XlsxResourceCatalog,
    find_xlsx_cells,
    find_xlsx_text,
    inspect_xlsx,
    parse_xlsx,
    query_xlsx,
)
from xlsx_llm_parser import ParseOptions as XlsxOptions

from .documents import Document, DocumentStore
from .models import ToolError, ToolResponse
from .presentation import Presenter
from .schemas import (
    BaseSourceArgs,
    BinaryArgs,
    DocxReadArgs,
    DocxResourceArgs,
    FindArgs,
    InspectArgs,
    PptxReadArgs,
    PptxResourceArgs,
    QueryArgs,
    TextFindArgs,
    XlsxReadArgs,
    XlsxResourceArgs,
)


class Operations:
    def __init__(self, documents: DocumentStore, presenter: Presenter) -> None:
        self.documents = documents
        self.presenter = presenter

    def inspect(self, document: Document, *, full_parse: bool = False) -> dict[str, Any]:
        if isinstance(document.options, XlsxOptions) and not full_parse:
            if document.index is None:
                document.index = inspect_xlsx(document.snapshot, options=document.options)
            index = cast(dict[str, Any], document.index)
            names = index.get("defined_names", [])
            value = {"format": "xlsx", "scope": "workbook-index", "sheet_count": index["sheet_count"], "sheets": index["sheets"]}
            if names:
                value["defined_names"] = names
            if index.get("external_links"):
                value["external_links"] = index["external_links"]
            return value
        described = cast(dict[str, Any], self.documents.session(document).describe())
        if full_parse:
            return {"path": str(document.original), "revision": document.revision, **described}
        navigation = dict(described["navigation"])
        if document.format == "pptx":
            slides = [
                {key: value for key, value in item.items() if value is not None and value is not False}
                for item in navigation.get("slides", [])
                if item.get("hidden") or item.get("section")
            ]
            navigation.pop("slides", None)
            if slides:
                navigation["slides"] = slides
        return {"format": document.format, "navigation": navigation}

    def run(self, name: str, document: Document, args: BaseSourceArgs) -> ToolResponse:
        if name == "inspect_document":
            assert isinstance(args, InspectArgs)
            return self.presenter.metadata(document, self.inspect(document, full_parse=args.full_parse))
        if isinstance(args, DocxReadArgs):
            self.require_format(document, "docx")
            return self.read_docx(document, args)
        if isinstance(args, PptxReadArgs):
            self.require_format(document, "pptx")
            return self.read_pptx(document, args)
        if isinstance(args, XlsxReadArgs):
            self.require_format(document, "xlsx")
            return self.read_xlsx(document, args)
        if isinstance(args, TextFindArgs):
            return self.find_text(document, args)
        if isinstance(args, FindArgs):
            self.require_format(document, "xlsx")
            if isinstance(document.session, XlsxReadSession):
                result = document.session.find_cells(args.query, sheets=args.sheets, kind=args.kind, limit=args.limit)
            else:
                assert isinstance(document.options, XlsxOptions)
                result = find_xlsx_cells(
                    document.snapshot, args.query, options=document.options, sheets=args.sheets, kind=args.kind, limit=args.limit
                )
            return self.presenter.parsed(document, [result])
        if isinstance(args, QueryArgs):
            self.require_format(document, "xlsx")
            where = cast(list[WhereCondition], [v.model_dump() for v in args.where]) if args.where is not None else None
            aggregates = (
                cast(list[AggregateSpec], [v.model_dump(by_alias=True, exclude_none=True) for v in args.aggregates])
                if args.aggregates is not None
                else None
            )
            order = cast(list[OrderSpec], [v.model_dump() for v in args.order_by]) if args.order_by is not None else None
            if isinstance(document.session, XlsxReadSession):
                execute_query = document.session.query_data
            else:
                assert isinstance(document.options, XlsxOptions)
                execute_query = partial(query_xlsx, document.snapshot, options=document.options)
            result = execute_query(
                table_id=args.table_id,
                sheet=args.sheet,
                range_spec=args.range_spec,
                header_row=args.header_row,
                select=args.select,
                where=where,
                group_by=args.group_by,
                aggregates=aggregates,
                order_by=order,
                limit=args.limit,
            )
            return self.presenter.parsed(document, [result])
        if name == "list_document_resources":
            if isinstance(document.options, XlsxOptions) and document.session is None:
                if document.resource_catalog is None:
                    with XlsxResourceCatalog(document.snapshot, options=document.options) as catalog:
                        document.resource_catalog = catalog.resources
                descriptors = document.resource_catalog
            else:
                descriptors = self.documents.session(document).resources
            resources = []
            for resource in descriptors:
                data = resource.to_dict()
                data["binary_readable"] = resource.source == "embedded" and resource.kind in (
                    {"image", "media"} if document.format == "pptx" else {"image"}
                )
                data["renderable"] = resource.kind in (
                    {"chart", "pivot_table"} if document.format == "xlsx" else {"chart", "smartart", "table"}
                )
                data["queryable"] = document.format == "xlsx" and resource.kind == "table"
                resources.append(data)
            return self.presenter.metadata(document, {"resources": resources})
        if isinstance(args, BinaryArgs):
            if isinstance(document.options, XlsxOptions) and document.session is None:
                with XlsxResourceCatalog(document.snapshot, options=document.options) as catalog:
                    descriptors = catalog.resources
                    descriptor = next((r for r in descriptors if r.kind == args.kind and r.id == args.resource_id), None)
                    if descriptor is None:
                        raise ToolError("RESOURCE_NOT_FOUND", "resource kind/id not found in this document snapshot")
                    value = catalog.read_resource(args.kind, args.resource_id)
            else:
                session = self.documents.session(document)
                descriptor = next((r for r in session.resources if r.kind == args.kind and r.id == args.resource_id), None)
                if descriptor is not None and descriptor.source != "external":
                    value = session.read_resource(args.kind, args.resource_id)
            if descriptor is None:
                raise ToolError("RESOURCE_NOT_FOUND", "resource kind/id not found in this document snapshot")
            if descriptor.source == "external":
                raise ToolError("EXTERNAL_RESOURCE", "external resources are not downloaded")
            media_type = descriptor.content_type or mimetypes.guess_type(descriptor.part or "")[0] or "application/octet-stream"
            return self.presenter.binary(document, value, media_type)
        if isinstance(args, DocxResourceArgs):
            self.require_format(document, "docx")
            docx = self.documents.session(document)
            assert isinstance(docx, DocxReadSession)
            result = docx.render_resource(
                args.kind,
                args.resource_id,
                rows=args.rows,
                columns=args.columns,
                aggregate=args.aggregate,
                aggregate_column=args.aggregate_column,
            )
        elif isinstance(args, PptxResourceArgs):
            self.require_format(document, "pptx")
            pptx = self.documents.session(document)
            assert isinstance(pptx, PptxReadSession)
            result = pptx.render_resource(
                args.kind,
                args.resource_id,
                rows=args.rows,
                columns=args.columns,
                aggregate=args.aggregate,
                aggregate_column=args.aggregate_column,
            )
        elif isinstance(args, XlsxResourceArgs):
            result = self.xlsx_session(document).render_resource(args.kind, args.resource_id)
        else:
            raise ToolError("UNKNOWN_TOOL", "operation is not implemented")
        return self.presenter.parsed(document, [result])

    @staticmethod
    def require_format(document: Document, format_name: str) -> None:
        if document.format != format_name:
            raise ToolError("FORMAT_MISMATCH", f"tool requires {format_name}, received {document.format}")

    def xlsx_session(self, document: Document) -> XlsxReadSession:
        self.require_format(document, "xlsx")
        session = self.documents.session(document)
        assert isinstance(session, XlsxReadSession)
        return session

    def find_text(self, document: Document, args: TextFindArgs) -> ToolResponse:
        if args.include_headers_footers and document.format != "docx":
            raise ToolError("INVALID_ARGUMENT", "include_headers_footers is supported only for DOCX")
        if args.sheets is not None and document.format != "xlsx":
            raise ToolError("INVALID_ARGUMENT", "sheets is supported only for XLSX")
        options = TextSearchOptions(args.case_sensitive, args.offset, args.limit, args.context_before, args.context_after)
        if isinstance(document.options, XlsxOptions) and document.session is None:
            result = find_xlsx_text(
                document.snapshot, args.query, options=document.options, search_options=options, sheets=args.sheets
            )
        elif isinstance((session := self.documents.session(document)), DocxReadSession):
            result = session.find_text(args.query, options=options, include_headers_footers=args.include_headers_footers)
        elif isinstance(session, PptxReadSession):
            result = session.find_text(args.query, options=options)
        else:
            result = session.find_text(args.query, options=options, sheets=args.sheets)
        items = [(match.text, {"selection": dict(match.locator), "media_type": "text/plain"}) for match in result.matches]
        return self.presenter.text_parts(document, items, extra={"next_offset": result.next_offset})

    def read_docx(self, document: Document, args: DocxReadArgs) -> ToolResponse:
        session = self.documents.session(document)
        assert isinstance(session, DocxReadSession)
        if args.whole_document:
            return self.presenter.parsed(document, [session.render(density=args.density)])
        navigation = cast(dict[str, Any], session.describe()["navigation"])
        total = cast(int, navigation["page_count"])
        requested_end = args.page_end if args.page_end is not None else args.page_start + 2
        if requested_end < args.page_start:
            raise ToolError("INVALID_ARGUMENT", "page_end must be at least page_start")
        end = min(requested_end, total)
        pages = range(args.page_start, max(args.page_start, end) + 1)
        content_pages = cast(list[int], navigation["content_pages"])
        parsed: list[ParseResult] = []
        for page in pages:
            result = session.render(density=args.density, page_hint=page, span=1)
            if page not in content_pages:
                result.selection["empty"] = True
            parsed.append(result)
        return self.presenter.parsed(
            document,
            parsed,
            extra={
                "page_count": total,
                **({"next_page": end + 1} if end < total else {}),
            },
        )

    def read_pptx(self, document: Document, args: PptxReadArgs) -> ToolResponse:
        session = self.documents.session(document)
        assert isinstance(session, PptxReadSession)
        if args.whole_document:
            return self.presenter.parsed(document, [session.render(density=args.density)])
        end = args.slide_end if args.slide_end is not None else args.slide_start + 2
        if end < args.slide_start:
            raise ToolError("INVALID_ARGUMENT", "slide_end must be at least slide_start")
        navigation = cast(dict[str, Any], session.describe()["navigation"])
        total = cast(int, navigation["slide_count"])
        result = session.render(density=args.density, slide=args.slide_start, span=end - args.slide_start + 1)
        return self.presenter.parsed(
            document, [result], extra={"slide_count": total, **({"next_slide": min(end, total) + 1} if end < total else {})}
        )

    def read_xlsx(self, document: Document, args: XlsxReadArgs) -> ToolResponse:
        orientation = self.inspect(document)
        sheets = cast(list[dict[str, Any]], orientation["sheets"])
        sheet = args.sheet
        if sheet is None:
            sheet = next((item["name"] for item in sheets if item.get("kind", "worksheet") == "worksheet"), None)
        extra = {"sheets": sheets} if args.sheet is None else {}
        if sheet is None:
            return self.presenter.metadata(document, {"parts": [], **extra})
        key = document.id + ":" + json.dumps(args.model_dump(exclude={"path", "document_id", "options"}), sort_keys=True)
        cached = self.presenter.results.cached(key)
        if cached is not None:
            return self.presenter.entries(document, [cached], extra=extra)
        if isinstance(document.session, XlsxReadSession):
            session = self.xlsx_session(document)
            result = session.render(density=args.density, sheet=sheet, range_spec=args.range_spec)
        else:
            assert isinstance(document.options, XlsxOptions)
            result = parse_xlsx(
                document.snapshot, density=args.density, sheet=sheet, range_spec=args.range_spec, options=document.options
            )
        return self.presenter.parsed(document, [result], cache_key=key, extra=extra)
