"""Public DOCX parsing and explicit read-session API."""

from __future__ import annotations

from collections.abc import Iterator

from ooxml_llm_core.models import Density, ParseReport, ParseResult, ResourceDescriptor
from ooxml_llm_core.session import SessionLifecycle

from ._api_support import Source, _density, _resource_descriptors, _result, _validate_window
from .core.enums import ResourceType
from .core.models import ParsedDocument, ParseOptions
from .core.package import PackageReader
from .parsing import get_render_pipeline
from .parsing.runner import DocxParser
from .plan import DocxParsePlan
from .rendering.dispatch import describe_pages, render_page_window, render_resource


class DocxReadSession:
    """Context-managed DOCX session with one package reader owner."""

    def __init__(self, source: Source, options: ParseOptions) -> None:
        self.source = source
        self.options = options
        self.parsed_document: ParsedDocument | None = None
        self._package: PackageReader | None = None
        self._lifecycle: SessionLifecycle[ParsedDocument] = SessionLifecycle("DOCX")

    def __enter__(self) -> DocxReadSession:
        self._lifecycle.check_new()
        self._package = PackageReader(self.source, self.options)
        package = self._package
        try:
            self.parsed_document = self._lifecycle.enter(
                package, lambda: DocxParser().parse(package, self.options, plan=DocxParsePlan.session())
            )
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._lifecycle.close()
        self._package = None
        self.parsed_document = None

    def _require_open(self) -> ParsedDocument:
        return self._lifecycle.require()

    @property
    def report(self) -> ParseReport:
        document = self._require_open()
        if document.report is None:  # pragma: no cover
            raise RuntimeError("parsed DOCX has no parse report")
        return document.report

    @property
    def resources(self) -> tuple[ResourceDescriptor, ...]:
        return _resource_descriptors(self._require_open())

    def describe(self) -> dict[str, object]:
        return {"format": "docx", "navigation": describe_pages(self._require_open()), "report": self.report.to_dict()}

    def render(
        self,
        *,
        density: Density | str = "semantic",
        page_hint: int | None = None,
        span: int = 1,
    ) -> ParseResult:
        document = self._require_open()
        resolved = _density(density)
        _validate_window(page_hint, span)
        if page_hint is None:
            text = "".join(get_render_pipeline(resolved).render(document))
            selection: dict[str, object] = {"kind": "all"}
        else:
            text = render_page_window(document, page_hint, span, resolved)
            selection = {"kind": "page_hint", "start": page_hint, "span": span}
        return _result(document, text, resolved, selection)

    def iter_render(
        self,
        *,
        density: Density | str = "semantic",
        page_hint: int | None = None,
        span: int = 1,
    ) -> Iterator[str]:
        document = self._require_open()
        resolved = _density(density)
        _validate_window(page_hint, span)
        if page_hint is None:
            chunks = get_render_pipeline(resolved).render(document)
        else:
            chunks = iter((render_page_window(document, page_hint, span, resolved),))

        def guarded() -> Iterator[str]:
            for chunk in chunks:
                self._require_open()
                yield chunk

        return guarded()

    def read_resource(self, kind: str, resource_id: str) -> bytes:
        document = self._require_open()
        if kind != "image":
            raise ValueError("DOCX binary resources currently support only 'image'")
        descriptor = next(
            (item for item in _resource_descriptors(document) if item.kind == kind and item.id == resource_id),
            None,
        )
        if descriptor is None:
            raise KeyError(f"resource {kind!r}/{resource_id!r} not found")
        if descriptor.source == "external":
            raise ValueError("external DOCX resources are not downloaded")
        if descriptor.part is None or self._package is None:
            raise RuntimeError("DOCX package reader is not open")
        return self._package.read_part(descriptor.part)

    def render_resource(
        self,
        kind: str,
        resource_id: str,
        *,
        rows: str | None = None,
        columns: list[str] | None = None,
        aggregate: str | None = None,
        aggregate_column: str | None = None,
    ) -> ParseResult:
        document = self._require_open()
        resource_type = ResourceType.parse(kind)
        if resource_type.is_plural:
            raise ValueError("resource kind must be singular")
        if resource_type is ResourceType.IMAGE:
            raise ValueError("use read_resource() for DOCX image bytes")
        rendered = render_resource(
            document,
            resource_type,
            resource_id,
            rows=rows,
            columns=columns,
            aggregate=aggregate,
            aggregate_column=aggregate_column,
        )
        if not rendered:
            raise KeyError(f"resource {kind!r}/{resource_id!r} not found")
        return _result(
            document,
            rendered[0],
            "semantic",
            {"kind": "resource", "resource_kind": kind, "id": resource_id},
            syntax_version="doctokens-xml/1.0",
            media_type="application/xml",
        )


def open_docx(source: Source, *, options: ParseOptions | None = None) -> DocxReadSession:
    return DocxReadSession(source, options or ParseOptions())


def parse_docx(
    source: Source,
    *,
    density: Density | str = "semantic",
    page_hint: int | None = None,
    span: int = 1,
    options: ParseOptions | None = None,
) -> ParseResult:
    resolved = _density(density)
    _validate_window(page_hint, span)
    plan = get_render_pipeline(resolved).plan
    document = DocxParser().parse(source, options or ParseOptions(), plan=plan)
    if page_hint is None:
        text = "".join(get_render_pipeline(resolved).render(document))
        selection: dict[str, object] = {"kind": "all"}
    else:
        text = render_page_window(document, page_hint, span, resolved)
        selection = {"kind": "page_hint", "start": page_hint, "span": span}
    return _result(document, text, resolved, selection)


__all__ = ["DocxReadSession", "open_docx", "parse_docx"]
