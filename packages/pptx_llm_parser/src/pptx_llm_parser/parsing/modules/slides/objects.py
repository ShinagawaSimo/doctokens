"""Objects."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.chart_ml import CHART_EX_GRAPHIC_DATA_URI
from ooxml_llm_core.models import ParseWarning

from ....core.constants import attr, first_child, local_name
from ....core.models import (
    AssetLookup,
    ChartLookup,
    LayoutLookup,
    ShapeBlock,
    SmartArtLookup,
    TableCell,
)
from .runs import _drawingml_bool, _parse_int, tx_body_text
from .shape_details import _find_descendant, _shape_alt, _shape_name


class SlideObjectParser:
    """Resolve slide resources and own presentation-wide table numbering."""

    def __init__(
        self,
        warnings: list[ParseWarning],
        assets: AssetLookup,
        charts: ChartLookup,
        smartarts: SmartArtLookup,
        layouts: LayoutLookup,
    ) -> None:
        self._warnings = warnings
        self._asset_lookup = assets
        self._chart_lookup = charts
        self._smartart_lookup = smartarts
        self._layout_lookup = layouts
        self._table_index = 0

    def _picture_shape(self, pic: ET.Element, part: str, ordinal: int) -> ShapeBlock | None:
        blip = _find_descendant(pic, "blip")
        if blip is None:
            self._warnings.append(ParseWarning(code="PICTURE_MISSING_BLIP", message="p:pic without a:blip", locator=part))
            return None
        rid = attr(blip, "r", "embed") or attr(blip, "r", "link")
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "picture",
            "name": _shape_name(pic) or "",
        }
        alt = _shape_alt(pic)
        if alt:
            shape["alt"] = alt
        if rid is None:
            self._warnings.append(ParseWarning(code="PICTURE_MISSING_RID", message="a:blip without r:embed/r:link", locator=part))
            return shape
        asset = self._asset_lookup.get((part, rid))
        if asset is None:
            self._warnings.append(
                ParseWarning(
                    code="PICTURE_ASSET_MISSING",
                    message=f"No asset relationship for {rid}",
                    locator=part,
                )
            )
            return shape
        shape["assetId"] = asset["id"]
        if asset.get("source") == "external":
            shape["href"] = asset.get("href", "")
        return shape

    def _media_shape(self, media: ET.Element, part: str, ordinal: int) -> ShapeBlock | None:
        rid = attr(media, "r", "embed")
        kind = "media"
        for element in media.iter():
            child_name = local_name(element.tag)
            if child_name == "videoFile":
                kind = "video"
                break
            if child_name == "audioFile":
                kind = "audio"
                break
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "media",
            "name": _shape_name(media) or "",
            "kind": kind,
        }
        if rid is None:
            self._warnings.append(ParseWarning(code="MEDIA_MISSING_RID", message="p14:media without r:embed", locator=part))
            return shape
        asset = self._asset_lookup.get((part, rid))
        if asset is None:
            self._warnings.append(
                ParseWarning(
                    code="MEDIA_ASSET_MISSING",
                    message=f"No media relationship for {rid}",
                    locator=part,
                )
            )
            return shape
        shape["assetId"] = asset["id"]
        if asset.get("source") == "external":
            shape["href"] = asset.get("href", "")
        return shape

    def _graphic_frame_shape(self, frame: ET.Element, part: str, ordinal: int) -> ShapeBlock | None:
        graphic_data = _find_descendant(frame, "graphicData")
        if graphic_data is None:
            self._warnings.append(
                ParseWarning(
                    code="GRAPHIC_FRAME_MISSING_DATA",
                    message="p:graphicFrame without a:graphicData",
                    locator=part,
                )
            )
            return None
        uri = graphic_data.get("uri", "")
        if uri == "http://schemas.openxmlformats.org/drawingml/2006/table":
            return self._table_shape(frame, part, ordinal)
        if uri == "http://schemas.openxmlformats.org/drawingml/2006/chart":
            return self._chart_shape(frame, part, ordinal)
        if uri == CHART_EX_GRAPHIC_DATA_URI:
            return self._chart_shape(frame, part, ordinal)
        if uri == "http://schemas.openxmlformats.org/drawingml/2006/diagram":
            return self._smartart_shape(frame, part, ordinal)
        self._warnings.append(
            ParseWarning(
                code="UNSUPPORTED_SHAPE_TYPE",
                message=f"Unsupported graphicFrame: {uri or '(no uri)'}",
                locator=part,
            )
        )
        return None

    def _chart_shape(self, frame: ET.Element, part: str, ordinal: int) -> ShapeBlock | None:
        chart_ref = _find_descendant(frame, "chart")
        if chart_ref is None:
            self._warnings.append(
                ParseWarning(
                    code="CHART_MISSING_REF",
                    message="chart graphicFrame without c:chart",
                    locator=part,
                )
            )
            return None
        rid = attr(chart_ref, "r", "id")
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "chart",
            "name": _shape_name(frame) or "",
        }
        if rid is None:
            self._warnings.append(ParseWarning(code="CHART_MISSING_RID", message="c:chart without r:id", locator=part))
            return shape
        chart = self._chart_lookup.get((part, rid))
        if chart is None:
            self._warnings.append(
                ParseWarning(
                    code="CHART_ASSET_MISSING",
                    message=f"No chart relationship for {rid}",
                    locator=part,
                )
            )
            return shape
        chart_id = chart.get("id")
        if chart_id:
            shape["chartId"] = chart_id
        chart_type = chart.get("chart_type")
        if chart_type:
            shape["chartType"] = chart_type
        series_count = chart.get("series_count")
        if series_count is not None:
            shape["seriesCount"] = series_count
        point_count = chart.get("point_count")
        if point_count is not None:
            shape["pointCount"] = point_count
        return shape

    def _smartart_shape(self, frame: ET.Element, part: str, ordinal: int) -> ShapeBlock | None:
        rel_ids = _find_descendant(frame, "relIds")
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "smartart",
            "name": _shape_name(frame) or "",
        }
        if rel_ids is None:
            self._warnings.append(
                ParseWarning(
                    code="SMARTART_MISSING_RELIDS",
                    message="diagram graphicFrame without dgm:relIds",
                    locator=part,
                )
            )
            return shape
        dm_rid = attr(rel_ids, "r", "dm")
        if dm_rid is None:
            self._warnings.append(ParseWarning(code="SMARTART_MISSING_DM", message="dgm:relIds without r:dm", locator=part))
            return shape
        smartart = self._smartart_lookup.get((part, dm_rid))
        if smartart is None:
            self._warnings.append(
                ParseWarning(
                    code="SMARTART_ASSET_MISSING",
                    message=f"No diagram data relationship for {dm_rid}",
                    locator=part,
                )
            )
            return shape
        smartart_id = smartart.get("id")
        if smartart_id:
            shape["smartartId"] = smartart_id
        node_count = smartart.get("nodeCount")
        if node_count is not None:
            shape["nodeCount"] = node_count
        link_count = smartart.get("linkCount")
        if link_count is not None:
            shape["linkCount"] = link_count
        lo_rid = attr(rel_ids, "r", "lo")
        if lo_rid is not None:
            category = self._layout_lookup.get((part, lo_rid))
            if category:
                shape["layoutType"] = category
        return shape

    def _table_shape(self, frame: ET.Element, part: str, ordinal: int) -> ShapeBlock | None:
        tbl = _find_descendant(frame, "tbl")
        if tbl is None:
            self._warnings.append(
                ParseWarning(code="TABLE_MISSING_TBL", message="graphicFrame table without a:tbl", locator=part)
            )
            return None
        rows: list[list[str]] = []
        table_cells: list[list[TableCell]] = []
        column_widths: list[int] = []
        grid = first_child(tbl, "a", "tblGrid")
        if grid is not None:
            for column in grid:
                if local_name(column.tag) == "gridCol":
                    width = _parse_int(column.get("w"), 0)
                    if width > 0:
                        column_widths.append(width)
        for child in tbl:
            if local_name(child.tag) != "tr":
                continue
            row: list[str] = []
            cell_row: list[TableCell] = []
            for cell in child:
                if local_name(cell.tag) != "tc":
                    continue
                tx_body = first_child(cell, "a", "txBody")
                text = tx_body_text(tx_body, part, self._warnings) or ""
                row.append(text)
                cell_info: TableCell = {"text": text}
                col_span = _parse_int(cell.get("gridSpan"), 1)
                row_span = _parse_int(cell.get("rowSpan"), 1)
                if col_span > 1:
                    cell_info["colSpan"] = col_span
                if row_span > 1:
                    cell_info["rowSpan"] = row_span
                if _drawingml_bool(cell.get("hMerge")):
                    cell_info["hMerge"] = True
                if _drawingml_bool(cell.get("vMerge")):
                    cell_info["vMerge"] = True
                cell_row.append(cell_info)
            rows.append(row)
            table_cells.append(cell_row)
        self._normalize_table_merges(table_cells)
        self._table_index += 1
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "table",
            "name": _shape_name(frame) or "",
            "rows": rows,
            "tableId": f"table{self._table_index}",
        }
        shape["tableCells"] = table_cells
        if column_widths:
            shape["columnWidths"] = column_widths
        return shape

    @staticmethod
    def _normalize_table_merges(rows: list[list[TableCell]]) -> None:
        """Infer spans when producers emit only hMerge/vMerge continuations."""
        explicit_row_spans = {id(cell) for row in rows for cell in row if "rowSpan" in cell}
        for row in rows:
            anchor: TableCell | None = None
            explicit_col_span = False
            for cell in row:
                if cell.get("hMerge"):
                    if anchor is not None and not explicit_col_span:
                        anchor["colSpan"] = anchor.get("colSpan", 1) + 1
                else:
                    anchor = cell
                    explicit_col_span = "colSpan" in cell
        for row_index, row in enumerate(rows):
            for column_index, cell in enumerate(row):
                if not cell.get("vMerge"):
                    continue
                for previous_index in range(row_index - 1, -1, -1):
                    previous_row = rows[previous_index]
                    if column_index >= len(previous_row):
                        continue
                    anchor = previous_row[column_index]
                    if anchor.get("vMerge"):
                        continue
                    if id(anchor) not in explicit_row_spans:
                        anchor["rowSpan"] = row_index - previous_index + 1
                    break
