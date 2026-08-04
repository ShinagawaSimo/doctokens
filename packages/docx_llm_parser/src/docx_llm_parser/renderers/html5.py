"""Internal HTML5 renderer orchestration and resource query helpers."""

from __future__ import annotations

import os
import zipfile
from collections.abc import Iterator
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter

from ..core.enums import Density, ResourceType
from ..core.models import DocumentManifest, ParsedDocument, ResourceDetail, TableBlock
from ._metrics import record_render_metrics, write_metrics_debug
from ._render import iter_l0, iter_l1, iter_l2
from .objects import extract_chart_item, extract_smartart_item

# ── 公共 API ──


def write_outputs(
    parsed: ParsedDocument,
    output_dir: Path,
    density: Density | str = Density.SEMANTIC,
) -> dict[str, str]:
    """写出最终标记文件，并在 metrics 中记录渲染耗时。"""
    resolved_density = Density.parse(density)
    output_dir.mkdir(parents=True, exist_ok=True)
    density_files = {
        Density.PLAIN: "l0.txt",
        Density.STRUCTURAL: "l1.html",
        Density.SEMANTIC: "parsed.html",
    }
    fname = density_files[resolved_density]
    output_path = output_dir / fname
    start = perf_counter()
    output_chars = 0
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=output_dir,
            prefix=f".{fname}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            for chunk in iter_html5(parsed, resolved_density):
                output_chars += len(chunk)
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        temp_path.replace(output_path)
    except Exception:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
        raise
    elapsed_ms = (perf_counter() - start) * 1000
    record_render_metrics(parsed, output_path, output_chars, elapsed_ms)
    write_metrics_debug(parsed)
    return {"html": str(output_path)}


def to_html5(parsed: ParsedDocument, density: Density | str = Density.SEMANTIC) -> str:
    """生成完整标记字符串（plain 纯文本 / structural 结构 / semantic 语义）。"""
    return "".join(iter_html5(parsed, density))


def iter_html5(parsed: ParsedDocument, density: Density | str = Density.SEMANTIC) -> Iterator[str]:
    """按片段生成标记，供大文档流式写出。"""
    resolved_density = Density.parse(density)
    if resolved_density is Density.PLAIN:
        yield from iter_l0(parsed)
    elif resolved_density is Density.STRUCTURAL:
        yield from iter_l1(parsed)
    else:
        yield from iter_l2(parsed)


def window(
    parsed: ParsedDocument,
    page: int,
    span: int = 1,
    density: Density | str = Density.SEMANTIC,
) -> str:
    """返回指定页码范围的内容片段。page=-1 表示最后一页。"""
    resolved_density = Density.parse(density)
    if page != -1 and page < 1:
        raise ValueError("page must be -1 or greater than zero")
    if span < 1:
        raise ValueError("span must be greater than zero")
    page_index = _build_page_index(parsed)
    total_pages = max(page_index.keys()) if page_index else 1

    if page == -1:
        start_page = total_pages
    elif page < 1:
        start_page = 1
    else:
        start_page = min(page, total_pages)

    end_page = min(start_page + span - 1, total_pages)

    start_block = page_index.get(start_page, (0,))[0] if start_page in page_index else 0
    end_block = page_index.get(end_page, (len(parsed.blocks) - 1,))
    end_idx = end_block[1] if isinstance(end_block, tuple) and len(end_block) > 1 else end_block[0]

    window_blocks = parsed.blocks[start_block : end_idx + 1]

    window_parsed = ParsedDocument(
        metadata=parsed.metadata,
        package_info=parsed.package_info,
        blocks=window_blocks,
        relationships=parsed.relationships,
        styles=parsed.styles,
        warnings=parsed.warnings,
        assets=parsed.assets,
        charts=parsed.charts,
        smartarts=parsed.smartarts,
        headers=[],
        footers=[],
        footnotes=parsed.footnotes,
        endnotes=parsed.endnotes,
        comments=[],
        numbering=parsed.numbering,
        metrics=parsed.metrics,
    )
    return "".join(iter_html5(window_parsed, resolved_density))


def manifest(parsed: ParsedDocument) -> DocumentManifest:
    """返回文档元信息，供 LLM 首轮调用获取概览。"""
    page_index = _build_page_index(parsed)
    pages = max(page_index.keys()) if page_index else 1
    return {
        "pages": pages,
        "tables": len(_table_groups(parsed)),
        "images": sum(1 for a in parsed.assets if a["type"] == "image"),
        "footnotes": len(parsed.footnotes),
        "endnotes": len(parsed.endnotes),
        "comments": len(parsed.comments),
    }


def extract(
    parsed: ParsedDocument,
    resource_type: ResourceType | str,
    resource_id: str | None = None,
    *,
    rows: str | None = None,
    columns: list[str] | None = None,
    aggregate: str | None = None,
    aggregate_column: str | None = None,
) -> list[ResourceDetail]:
    """独立提取非文本资源，无需先取全文。

    表格支持 ``rows``（行范围 ``"10-25"``，1-based 含两端）、
    ``columns``（按表头名称筛选）、``aggregate``（sum/count/avg/min/max，
    需配合 ``aggregate_column``）。
    """
    resolved_type = ResourceType.parse(resource_type)
    if resolved_type.is_plural and resource_id is not None:
        raise ValueError("resource_id is only valid with a singular resource type")
    if not resolved_type.is_plural and resource_id is None:
        raise ValueError("resource_id is required with a singular resource type")

    if resolved_type in {ResourceType.IMAGES, ResourceType.IMAGE}:
        source_path = parsed.metadata.get("sourcePath", "")
        result = []
        for a in parsed.assets:
            if a["type"] != "image":
                continue
            if resource_id and a["id"] != resource_id:
                continue
            item: ResourceDetail = {"id": a["id"]}
            if a.get("href"):
                item["href"] = a["href"]
            if a.get("contentType"):
                item["contentType"] = a["contentType"]
            # 从原始 ZIP 中按需读取图片二进制数据
            zip_path = a.get("zipPath")
            if zip_path and source_path:
                with zipfile.ZipFile(source_path, "r") as zf:
                    item["data"] = zf.read(zip_path)
            result.append(item)
        return result

    if resolved_type in {ResourceType.CHARTS, ResourceType.CHART}:
        result = []
        for c in parsed.charts:
            if resource_id and c.get("id") != resource_id:
                continue
            result.append(extract_chart_item(c))
        return result

    if resolved_type in {ResourceType.SMARTARTS, ResourceType.SMARTART}:
        result = []
        for s in parsed.smartarts:
            if resource_id and s.get("id") != resource_id:
                continue
            result.append(extract_smartart_item(s))
        return result

    if resolved_type is ResourceType.TABLES:
        return [
            _table_summary(table_id, segments)
            for table_id, segments in _table_groups(parsed).items()
        ]

    if resolved_type is ResourceType.TABLE:
        assert resource_id is not None
        segments = _table_groups(parsed).get(resource_id)
        if segments is None:
            return []
        item = _table_summary(resource_id, segments)
        all_rows = [row for segment in segments for row in segment["rows"]]
        if aggregate is not None:
            agg_result = _compute_aggregate(all_rows, aggregate, aggregate_column or "")
            item.update(agg_result)
        else:
            item["rows"] = _slice_and_filter_rows(all_rows, rows, columns)
        return [item]

    raise AssertionError("validated resource type was not handled")


def _table_groups(parsed: ParsedDocument) -> dict[str, list[TableBlock]]:
    """Group top-level table segments by their stable logical table ID."""
    groups: dict[str, list[TableBlock]] = {}
    for block in parsed.blocks:
        if block["type"] != "table":
            continue
        groups.setdefault(block["tableId"], []).append(block)
    return groups


def _table_summary(table_id: str, segments: list[TableBlock]) -> ResourceDetail:
    """Build a stable summary for one logical table."""
    return {
        "id": table_id,
        "rowCount": sum(len(segment["rows"]) for segment in segments),
        "columnCount": max((segment["columnCount"] for segment in segments), default=0),
        "segmentCount": len(segments),
        "pages": [segment.get("page", 1) for segment in segments],
    }


def _slice_and_filter_rows(
    rows: list,
    rows_spec: str | None,
    columns: list[str] | None,
) -> list:
    """Apply row slicing and column filtering to table rows.

    Column filtering is applied first (needs header row for name matching),
    then row slicing operates on the already-filtered result.
    """
    if columns is not None:
        rows = _filter_columns(rows, columns)
    if rows_spec is not None:
        rows = _slice_rows(rows, rows_spec)
    return rows


def _slice_rows(rows: list, spec: str) -> list:
    """Slice rows by range like ``"10-25"`` (1-based, inclusive)."""
    try:
        start_str, end_str = spec.split("-", 1)
        start = int(start_str) - 1
        end = int(end_str)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid rows range: {spec!r}") from None
    if start < 0 or end < start:
        raise ValueError(f"Invalid rows range: {spec!r}")
    return rows[start:end]


def _filter_columns(rows: list, column_names: list[str]) -> list:
    """Keep only the columns whose header text matches one of *column_names*."""
    if not rows:
        return rows
    header = rows[0]
    header_texts = [cell["text"] for cell in header["cells"]]
    keep_indices = []
    for name in column_names:
        for idx, hdr_text in enumerate(header_texts):
            if hdr_text == name and idx not in keep_indices:
                keep_indices.append(idx)
                break
    keep_indices.sort()
    result = []
    for row in rows:
        filtered = [row["cells"][i] for i in keep_indices if i < len(row["cells"])]
        result.append({"rowIndex": row["rowIndex"], "cells": filtered, "isHeader": row.get("isHeader", False)})
    return result


_AGGREGATORS = {
    "sum": sum,
    "count": len,
    "avg": lambda vals: sum(vals) / len(vals) if vals else 0,
    "min": lambda vals: min(vals) if vals else 0,
    "max": lambda vals: max(vals) if vals else 0,
}


def _compute_aggregate(rows: list, operation: str, column: str) -> ResourceDetail:
    """Compute an aggregate over a named column; returns dict to merge into table item."""
    operation = operation.lower()
    if operation not in _AGGREGATORS:
        raise ValueError(
            f"Unknown aggregate {operation!r}; expected one of: {', '.join(sorted(_AGGREGATORS))}"
        )
    values = _column_values(rows, column)
    return {"aggregate": operation, "aggregate_column": column, "aggregate_value": _AGGREGATORS[operation](values)}


def _column_values(rows: list, column: str) -> list[float]:
    """Extract numeric values from a named column (matched by header text)."""
    if not rows:
        return []
    header = rows[0]
    col_idx: int | None = None
    for idx, cell in enumerate(header["cells"]):
        if cell["text"] == column:
            col_idx = idx
            break
    if col_idx is None:
        raise ValueError(f"Column {column!r} not found in table header")
    values: list[float] = []
    for row in rows[1:]:  # skip header row
        if col_idx >= len(row["cells"]):
            continue
        text = row["cells"][col_idx].get("text", "").strip()
        if not text:
            continue
        try:
            values.append(float(text))
        except ValueError:
            continue
    return values


# ── 页码索引 ──


def _build_page_index(parsed: ParsedDocument) -> dict[int, tuple[int, int]]:
    """构建 page → (start_block_idx, end_block_idx) 映射。"""
    index: dict[int, tuple[int, int]] = {}
    current_page = 1
    page_start = 0

    for i, block in enumerate(parsed.blocks):
        block_page = block.get("page", 1)
        if block_page != current_page:
            index[current_page] = (page_start, i - 1)
            current_page = block_page
            page_start = i

    if parsed.blocks:
        index[current_page] = (page_start, len(parsed.blocks) - 1)
    else:
        index[1] = (0, -1)

    return index
