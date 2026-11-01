"""Project only intersecting and explicitly dependent worksheet context."""

from __future__ import annotations

from ..model.workbook import Cell, DefinedName, ParsedWorkbook, SheetInfo, WorkbookMetadata
from .context_references import Bounds, intersects, references, relevant_range
from .selection import MAX_COLUMN


def range_context(
    workbook: ParsedWorkbook, sheet: SheetInfo, selected: Bounds, rows: list[list[Cell]]
) -> tuple[ParsedWorkbook, SheetInfo]:
    """Use shallow projections; never modify the reusable session workbook."""
    projected: SheetInfo = {**sheet}
    projected["hidden_cols"] = [
        (max(first, selected[0]), min(last, selected[2]))
        for first, last in sheet.get("hidden_cols", [])
        if first <= selected[2] and selected[0] <= last
    ]
    projected["data_validations"] = [
        v for v in sheet.get("data_validations", []) if relevant_range(v.get("ranges", ""), selected)
    ]
    projected["conditional_formats"] = [
        v for v in sheet.get("conditional_formats", []) if relevant_range(v.get("ranges", ""), selected)
    ]
    # Filtering affects entire row visibility, including cells in other columns.
    filter_rows = (1, selected[1], MAX_COLUMN, selected[3])
    if not relevant_range(sheet.get("filter_range", ""), filter_rows):
        projected.pop("filter_range", None)
        projected.pop("filter_cols", None)
    projected["pivot_tables"] = [v for v in sheet.get("pivot_tables", []) if relevant_range(v.get("ref", ""), selected)]
    projected["tables"] = [v for v in sheet.get("tables", []) if relevant_range(v.get("ref", ""), selected)]
    expressions = [cell["formula"] for row in rows for cell in row if cell.get("formula")]
    expressions.extend(cell["hyperlink"][1:] for row in rows for cell in row if cell.get("hyperlink", "").startswith("#"))
    expressions.extend(v[key] for v in projected["data_validations"] for key in ("formula1", "formula2") if v.get(key))
    expressions.extend(f for rule in projected["conditional_formats"] for f in rule.get("formulas", []))
    for rule in projected["conditional_formats"]:
        details = rule.get("formatDetails", {})
        for stops in (details.get("stops", []), details.get("thresholds", [])):
            expressions.extend(stop["val"] for stop in stops if stop.get("type") == "formula" and "val" in stop)
    names, used_tables, external = _dependencies(workbook, sheet, selected, expressions)
    projected["tables"] = [
        table
        for table in sheet.get("tables", [])
        if table in projected["tables"] or table.get("name", "").casefold() in used_tables
    ]
    _project_drawings(projected, sheet, selected)
    metadata: WorkbookMetadata = {"defined_names": names, "external_links": external}
    caches = {pivot["cacheRef"] for pivot in projected["pivot_tables"] if "cacheRef" in pivot}
    original = workbook["metadata"]
    metadata["pivot_caches"] = [cache for cache in original.get("pivot_caches", []) if cache.get("id") in caches]
    metadata["slicers"] = [item for item in original.get("slicers", []) if item.get("cacheRef") in caches]
    metadata["timelines"] = [item for item in original.get("timelines", []) if item.get("cacheRef") in caches]
    return {**workbook, "metadata": metadata}, projected


def _dependencies(
    workbook: ParsedWorkbook, sheet: SheetInfo, selected: Bounds, expressions: list[str]
) -> tuple[list[DefinedName], set[str], list[str]]:
    available = workbook["metadata"].get("defined_names", [])
    by_name = {
        (item["scopeSheet"].casefold() if item["scopeSheet"] else None, item["name"].casefold()): index
        for index, item in enumerate(available)
    }
    sheet_name = sheet["name"].casefold()
    retained: set[int] = set()
    queue = [(expr, sheet_name) for expr in expressions]
    # Names directly designating selected cells are useful context in their own right.
    for index, item in enumerate(available):
        scope = item["scopeSheet"]
        if item.get("hidden") or item["name"].startswith("_xlnm.") or (scope and scope.casefold() != sheet_name):
            continue
        refs = references(item["ref"])
        if any(
            (qualifier or (scope.casefold() if scope else sheet_name)) == sheet_name and intersects(area, selected)
            for qualifier, area in refs.areas
        ):
            retained.add(index)
            queue.append((item["ref"], scope.casefold() if scope else sheet_name))
    tables: set[str] = set()
    external: set[str] = set()
    while queue:
        expr, context_sheet = queue.pop()
        refs = references(expr)
        external.update(refs.external)
        for qualifier, name in refs.names:
            scope = qualifier or context_sheet
            dependency = by_name.get((scope, name), by_name.get((None, name)))
            if dependency is not None and dependency not in retained:
                retained.add(dependency)
                item = available[dependency]
                queue.append((item["ref"], item["scopeSheet"].casefold() if item["scopeSheet"] else context_sheet))
            if qualifier is None or qualifier == sheet_name:
                tables.add(name)
    targets = {target.casefold(): target for target in external}
    for target in workbook["metadata"].get("external_links", []):
        if target.casefold() in targets:
            targets[target.casefold()] = target
    return [item for index, item in enumerate(available) if index in retained], tables, sorted(targets.values())


def _project_drawings(projected: SheetInfo, original: SheetInfo, selected: Bounds) -> None:
    all_objects = [*original.get("images", []), *original.get("charts", []), *original.get("drawing_shapes", [])]
    by_id = {item["id"]: item for item in all_objects if item.get("id")}
    connectors: dict[str, list[str]] = {}
    for connector in original.get("drawing_shapes", []):
        for key in ("fromShape", "toShape"):
            if connector.get(key) and connector.get("id"):
                connectors.setdefault(connector[key], []).append(connector["id"])
    retained = {
        item["id"]
        for item in all_objects
        if item.get("id") and relevant_range(item.get("anchorRange") or item.get("ref", ""), selected)
    }
    queue = list(retained)
    while queue:
        identifier = queue.pop()
        item = by_id[identifier]
        targets = [item.get(key) for key in ("group", "fromShape", "toShape")]
        targets.extend(connectors.get(identifier, []))
        for target in targets:
            if target in by_id and target not in retained:
                retained.add(target)
                queue.append(target)
    projected["images"] = [item for item in original.get("images", []) if item.get("id") in retained]
    projected["charts"] = [item for item in original.get("charts", []) if item.get("id") in retained]
    projected["drawing_shapes"] = [item for item in original.get("drawing_shapes", []) if item.get("id") in retained]
