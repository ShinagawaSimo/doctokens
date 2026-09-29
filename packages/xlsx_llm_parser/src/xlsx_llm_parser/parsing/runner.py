"""XLSX parser — read workbook and worksheet data from an OPC package."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from xml.etree import ElementTree as ET

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.metrics import MetricsRecorder
from ooxml_llm_core.models import ParseReport, ParseWarning
from ooxml_llm_core.package import PackageReader

from ..models import (
    ParsedWorkbook,
    ParseOptions,
)
from ..plan import XlsxFeature, XlsxParsePlan
from .modules.styles.index import parse_styles
from .modules.workbook.features import CellControlCatalog
from .modules.workbook.metadata import _parse_shared_strings, _parse_workbook_xml
from .modules.workbook.pivots import PivotCatalog
from .modules.workbook.rich_values import RichValueCatalog
from .modules.worksheets.comments import parse_threaded_comment_people
from .modules.worksheets.drawings import parse_drawings
from .modules.worksheets.post import (
    parse_tables,
)
from .modules.worksheets.scanner import parse_sheet


# OOXML cell type codes -> LLM-readable semantic names.
def _parse_workbook(
    source: str | Path | bytes | PackageReader,
    options: ParseOptions | None = None,
    *,
    plan: XlsxParsePlan | None = None,
) -> ParsedWorkbook:
    """Parse an XLSX file and return a typed workbook IR."""
    parse_options = options or ParseOptions()
    parse_plan = plan or XlsxParsePlan.session()
    limits = PackageLimits(
        max_zip_entries=parse_options.max_zip_entries,
        max_entry_uncompressed_bytes=parse_options.max_entry_uncompressed_bytes,
        max_total_uncompressed_bytes=parse_options.max_total_uncompressed_bytes,
    )
    metrics = MetricsRecorder()
    metrics.set_counter("moduleCount", len(parse_plan.module_keys))
    metrics.set_counter("modules", ",".join(parse_plan.module_keys))
    warnings: list[ParseWarning] = []
    with metrics.stage("parse"), _open_package(source, limits) as package_reader:
        package_reader.validate(required_part="xl/workbook.xml")

        date_1904, worksheet_infos, defined_names, external_links = _parse_workbook_xml(
            package_reader,
            include_defined_names=parse_plan.needs(XlsxFeature.DEFINED_NAMES),
            include_external_links=parse_plan.needs(XlsxFeature.EXTERNAL_LINKS),
        )
        if parse_plan.sheet_names is not None:
            worksheet_infos = [sheet_info for sheet_info in worksheet_infos if sheet_info["name"] in parse_plan.sheet_names]
        shared_strings, rich_text_map = _parse_shared_strings(
            package_reader,
            include_rich_text=parse_plan.needs(XlsxFeature.RICH_TEXT),
        )
        rich_values = (
            RichValueCatalog.from_package(package_reader, warnings=warnings)
            if parse_plan.needs(XlsxFeature.RICH_VALUES)
            else RichValueCatalog()
        )
        cell_controls = (
            CellControlCatalog.from_package(package_reader, warnings=warnings)
            if parse_plan.needs(XlsxFeature.CELL_CONTROLS)
            else CellControlCatalog()
        )
        pivot_catalog = (
            PivotCatalog.from_package(package_reader, warnings=warnings)
            if parse_plan.needs(XlsxFeature.PIVOTS)
            else PivotCatalog()
        )
        format_index = parse_styles(
            package_reader,
            detail=parse_plan.style_detail,  # type: ignore[arg-type]
            locale=parse_options.locale,
        )
        format_index.set_cell_controls(cell_controls.by_style)
        format_index.set_date_system(date_1904)
        threaded_comment_people = (
            parse_threaded_comment_people(package_reader, warnings) if parse_plan.needs(XlsxFeature.COMMENTS) else {}
        )
        next_table_index = 0
        next_image_index = 1
        next_chart_index = 1
        next_pivot_index = 1

        for sheet_info in worksheet_infos:
            if sheet_info.get("kind") != "chartsheet":
                # Read sheet relationships once — shared across all helpers.
                try:
                    sheet_relationships = list(package_reader.read_relationships_for_part(sheet_info["part"]))
                except (ET.ParseError, KeyError, ValueError) as exc:
                    part = sheet_info["part"]
                    warnings.append(ParseWarning("SHEET_RELS_INVALID", f"Invalid worksheet relationships: {exc}", part))
                    sheet_relationships = []

                sheet_result = parse_sheet(
                    package_reader,
                    sheet_info["part"],
                    shared_strings,
                    rich_text_map,
                    format_index,
                    sheet_relationships,
                    threaded_comment_people,
                    rich_values,
                    plan=parse_plan,
                    cell_window=parse_plan.cell_window,
                )
                sheet_info["rows"] = sheet_result.rows
                if sheet_result.hidden_cols:
                    sheet_info["hidden_cols"] = sheet_result.hidden_cols
                if sheet_result.sheet_protection:
                    sheet_info["sheet_protection"] = True
                if sheet_result.filter_range:
                    sheet_info["filter_range"] = sheet_result.filter_range
                if sheet_result.filter_cols:
                    sheet_info["filter_cols"] = sheet_result.filter_cols
                if sheet_result.data_validations:
                    sheet_info["data_validations"] = sheet_result.data_validations
                if sheet_result.conditional_formats:
                    sheet_info["conditional_formats"] = sheet_result.conditional_formats
                warnings.extend(sheet_result.warnings)

                # Parse tables (ListObject) associated with this sheet
                tables = (
                    parse_tables(sheet_relationships, package_reader, start_index=next_table_index, warnings=warnings)
                    if parse_plan.needs(XlsxFeature.TABLES)
                    else []
                )
                next_table_index += len(tables)
                sheet_info["tables"] = tables

                # Parse drawing (images, shapes) + charts + pivots
                images, charts = (
                    parse_drawings(
                        sheet_relationships,
                        package_reader,
                        image_start=next_image_index,
                        chart_start=next_chart_index,
                        warnings=warnings,
                    )
                    if parse_plan.needs(XlsxFeature.DRAWINGS)
                    else ([], [])
                )
                next_image_index += len(images)
                next_chart_index += len(charts)
                if images:
                    sheet_info["images"] = images
                if charts:
                    sheet_info["charts"] = charts
                pivots = (
                    pivot_catalog.tables_for_relationships(sheet_relationships, start_index=next_pivot_index)
                    if parse_plan.needs(XlsxFeature.PIVOTS)
                    else []
                )
                next_pivot_index += len(pivots)
                if pivots:
                    sheet_info["pivot_tables"] = pivots

    workbook_manifest: dict[str, object] = {
        "sheetCount": len(worksheet_infos),
        "cellCount": sum(len(row) for sheet in worksheet_infos for row in sheet.get("rows", [])),
        "tableCount": sum(len(sheet.get("tables", [])) for sheet in worksheet_infos),
        "imageCount": sum(len(sheet.get("images", [])) for sheet in worksheet_infos),
        "chartCount": sum(len(sheet.get("charts", [])) for sheet in worksheet_infos),
        "pivotTableCount": sum(len(sheet.get("pivot_tables", [])) for sheet in worksheet_infos),
    }
    metrics.set_counter("sheetCount", len(worksheet_infos))
    metrics.set_counter("cellCount", workbook_manifest["cellCount"] if isinstance(workbook_manifest["cellCount"], int) else 0)
    metrics.set_counter("tableCount", workbook_manifest["tableCount"] if isinstance(workbook_manifest["tableCount"], int) else 0)
    metrics.set_counter("imageCount", workbook_manifest["imageCount"] if isinstance(workbook_manifest["imageCount"], int) else 0)
    metrics.set_counter("chartCount", workbook_manifest["chartCount"] if isinstance(workbook_manifest["chartCount"], int) else 0)
    metrics.set_counter(
        "pivotTableCount",
        workbook_manifest["pivotTableCount"] if isinstance(workbook_manifest["pivotTableCount"], int) else 0,
    )
    report = ParseReport("xlsx", 1, workbook_manifest, tuple(warnings), metrics.snapshot())
    return {
        "sheets": worksheet_infos,
        "fmt_index": format_index,
        "metadata": {
            "source": str(source) if isinstance(source, (str, Path)) else "<bytes>",
            "defined_names": defined_names,
            "external_links": external_links,
            "pivot_caches": pivot_catalog.caches,
            "slicers": pivot_catalog.slicers,
            "timelines": pivot_catalog.timelines,
        },
        "report": report,
    }


@contextmanager
def _open_package(source: str | Path | bytes | PackageReader, limits: PackageLimits) -> Iterator[PackageReader]:
    if isinstance(source, PackageReader):
        yield source
        return
    with PackageReader(source, limits) as package:
        yield package
