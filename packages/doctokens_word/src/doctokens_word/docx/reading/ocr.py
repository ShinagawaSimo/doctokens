"""Prepare only the images visible in a selected DOCX reading projection."""

from doctokens_core.runtime.image_ocr import ImageOcrReader

from ..model import ParsedDocument
from ..ooxml.package import PackageReader
from ..rendering.window_assets import referenced_image_ids


def prepare_ocr(reader: ImageOcrReader, package: PackageReader, document: ParsedDocument, density: str) -> None:
    if reader.provider is None:
        return
    used = referenced_image_ids(document, density)
    sources = [
        (asset["id"], asset["zipPath"])
        for asset in document.assets
        if asset["id"] in used and asset.get("source") == "embedded" and asset.get("zipPath")
    ]
    reader.prepare(package.read_part, sources, document.ocr_results, document.warnings)
    if document.report is not None:
        document.report = reader.report(document.report, document.ocr_results, document.warnings)
        document.metrics = document.report.metrics
