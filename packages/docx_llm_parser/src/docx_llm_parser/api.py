"""Public DOCX parsing and explicit read-session API."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ooxml_llm_core.models import Density, ParseReport, ParseResult, ResourceDescriptor

from .core.enums import ResourceType
from .core.models import ParsedDocument, ParseOptions
from .core.package import PackageReader
from .parsing import get_render_pipeline
from .parsing.runner import DocxParser
from .plan import DocxParsePlan
from .rendering.dispatch import render_page_window, render_resource
from .rendering.objects.resources import table_groups

Source = str | Path | bytes


def _density(value: Density | str) -> Density:
    if value not in {"plain", "structural", "semantic"}:
        raise ValueError("density must be one of: 'plain', 'structural', 'semantic'")
    return value


def _validate_window(page_hint: int | None, span: int) -> None:
    if page_hint is not None and (
        isinstance(page_hint, bool) or not isinstance(page_hint, int) or page_hint == 0 or page_hint < -1
    ):
        raise ValueError("page_hint must be -1 or a positive integer")
    if isinstance(span, bool) or not isinstance(span, int) or span <= 0:
        raise ValueError("span must be a positive integer")
    if page_hint is None and span != 1:
        raise ValueError("span requires page_hint")


def _resource_descriptors(document: ParsedDocument) -> tuple[ResourceDescriptor, ...]:
    descriptors: list[ResourceDescriptor] = []
    for asset in document.assets:
        source = "external" if asset.get("source") == "external" else "embedded"
        descriptors.append(
            ResourceDescriptor(
                id=asset["id"],
                kind=str(asset.get("type", "image")),
                source=source,  # type: ignore[arg-type]
                locator=asset.get("zipPath") or asset.get("href") or asset["id"],
                content_type=asset.get("contentType"),
                part=asset.get("zipPath"),
                external_target=asset.get("href"),
            )
        )
    descriptors.extend(
        ResourceDescriptor(chart["id"], "chart", "embedded", chart.get("part", chart["id"]), part=chart.get("part"))
        for chart in document.charts
    )
    descriptors.extend(
        ResourceDescriptor(
            smartart["id"],
            "smartart",
            "embedded",
            smartart.get("part", smartart["id"]),
            part=smartart.get("part"),
        )
        for smartart in document.smartarts
    )
    descriptors.extend(ResourceDescriptor(table_id, "table", "embedded", table_id) for table_id in table_groups(document))
    return tuple(descriptors)


def _result(document: ParsedDocument, text: str, density: Density, selection: dict[str, object]) -> ParseResult:
    if document.report is None:  # pragma: no cover - parser always attaches a report
        raise RuntimeError("parsed DOCX has no parse report")
    return ParseResult(text, density, selection, document.report, _resource_descriptors(document))


class DocxReadSession:
    """Context-managed DOCX session with one package reader owner."""

    def __init__(self, source: Source, options: ParseOptions) -> None:
        self.source = source
        self.options = options
        self.parsed_document: ParsedDocument | None = None
        self._package: PackageReader | None = None
        self._state = "new"

    def __enter__(self) -> DocxReadSession:
        if self._state != "new":
            raise RuntimeError("DOCX session cannot be entered twice")
        self._package = PackageReader(self.source, self.options)
        try:
            self._package.__enter__()
            self.parsed_document = DocxParser().parse(self._package, self.options, plan=DocxParsePlan.session())
        except BaseException:
            self.close()
            raise
        self._state = "open"
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self._state == "closed":
            return
        if self._package is not None:
            self._package.__exit__(None, None, None)
            self._package = None
        self.parsed_document = None
        self._state = "closed"

    def _require_open(self) -> ParsedDocument:
        if self._state != "open" or self.parsed_document is None:
            raise RuntimeError("DOCX session is not open")
        return self.parsed_document

    @property
    def report(self) -> ParseReport:
        document = self._require_open()
        if document.report is None:  # pragma: no cover
            raise RuntimeError("parsed DOCX has no parse report")
        return document.report

    @property
    def resources(self) -> tuple[ResourceDescriptor, ...]:
        return _resource_descriptors(self._require_open())

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
        return _result(document, rendered[0], "semantic", {"kind": "resource", "resource_kind": kind, "id": resource_id})


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
