"""Prepare only images rendered by the selected PPTX slides and density."""

from doctokens_core.runtime.image_ocr import ImageOcrReader

from ..model.presentation import ParsedPresentation
from ..ooxml.package import PackageReader


def prepare_ocr(reader: ImageOcrReader, package: PackageReader, presentation: ParsedPresentation, density: str) -> None:
    if reader.provider is None:
        return
    used = {
        shape["assetId"]
        for slide in presentation.slides
        for shape in slide["shapes"]
        if shape["type"] == "picture" and shape.get("assetId")
    }
    if density == "semantic":
        used.update(
            background["assetId"]
            for slide in presentation.slides
            if (background := slide.get("background")) and background.get("assetId")
        )
    sources = [
        (asset["id"], asset["zipPath"])
        for asset in presentation.assets
        if asset.get("id") in used and asset.get("type") == "image" and asset.get("source") == "embedded" and asset.get("zipPath")
    ]
    reader.prepare(package.read_part, sources, presentation.ocr_results, presentation.warnings)
    if presentation.report is not None:
        presentation.report = reader.report(presentation.report, presentation.ocr_results, presentation.warnings)
        presentation.metrics = presentation.report.metrics
