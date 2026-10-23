"""Resource-only workbook lifecycle, without shared strings or worksheet cells."""

from __future__ import annotations

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.models import ResourceDescriptor
from ooxml_llm_core.package import PackageReader
from ooxml_llm_core.session import SessionLifecycle

from ._api_support import Source
from ._resources import _resource_descriptors
from .models import ParsedWorkbook, ParseOptions
from .parsing.runner import _parse_workbook
from .plan import XlsxParsePlan


class XlsxResourceCatalog:
    """Context-managed directory and original image access; no cell operations."""

    def __init__(self, source: Source, *, options: ParseOptions | None = None) -> None:
        self.source = source
        self.options = options or ParseOptions()
        self._lifecycle: SessionLifecycle[ParsedWorkbook] = SessionLifecycle("XLSX resource catalog")
        self._package: PackageReader | None = None

    def __enter__(self) -> XlsxResourceCatalog:
        self._lifecycle.check_new()
        options = self.options
        package = PackageReader(
            self.source,
            PackageLimits(options.max_zip_entries, options.max_entry_uncompressed_bytes, options.max_total_uncompressed_bytes),
        )
        self._package = package
        try:
            self._lifecycle.enter(package, lambda: _parse_workbook(package, options, plan=XlsxParsePlan.resource("image")))
        except BaseException:
            self._package = None
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._lifecycle.close()
        self._package = None

    @property
    def resources(self) -> tuple[ResourceDescriptor, ...]:
        return _resource_descriptors(self._lifecycle.require())

    def read_resource(self, kind: str, resource_id: str) -> bytes:
        resources = self.resources
        if kind != "image":
            raise ValueError("XLSX binary resources currently support only 'image'")
        descriptor = next((item for item in resources if item.kind == kind and item.id == resource_id), None)
        if descriptor is None:
            raise KeyError(f"resource {kind!r}/{resource_id!r} not found")
        if descriptor.part is None or self._package is None:
            raise ValueError(f"resource {kind!r}/{resource_id!r} has no readable package part")
        return self._package.read_part(descriptor.part)
