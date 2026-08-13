"""Slide XML parsing: shape dispatch (text, picture, media)."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning

from ..core.constants import attr, first_child, local_name
from ..core.models import (
    AssetLookup,
    ChartLookup,
    LayoutContext,
    LayoutLookup,
    ShapeBlock,
    SmartArtLookup,
)
from ..ooxml.inheritance import LayoutMasterResolver, shape_geometry


class SlideParser:
    """Extract per-slide shapes from slide part XML, in geometric reading order."""

    def __init__(
        self,
        warnings: list[ParseWarning],
        asset_lookup: AssetLookup,
        chart_lookup: ChartLookup,
        smartart_lookup: SmartArtLookup,
        layout_lookup: LayoutLookup,
        resolver: LayoutMasterResolver,
        slide_size: tuple[int, int] | None,
    ) -> None:
        self._warnings = warnings
        self._asset_lookup = asset_lookup
        self._chart_lookup = chart_lookup
        self._smartart_lookup = smartart_lookup
        self._layout_lookup = layout_lookup
        self._resolver = resolver
        self._slide_size = slide_size

    def parse_slide(self, root: ET.Element, part: str) -> tuple[bool, list[ShapeBlock]]:
        """Return (hidden, shapes) for one p:sld root."""
        if local_name(root.tag) != "sld":
            self._warnings.append(
                ParseWarning(
                    code="SLIDE_INVALID_ROOT",
                    message=f"Slide root element is not p:sld: {root.tag}",
                    locator=part,
                )
            )
        hidden = root.get("show") == "0"
        return hidden, self._shapes(root, part)

    def _shapes(self, root: ET.Element, part: str) -> list[ShapeBlock]:
        c_sld = first_child(root, "p", "cSld")
        sp_tree = first_child(c_sld, "p", "spTree") if c_sld is not None else None
        if sp_tree is None:
            self._warnings.append(
                ParseWarning(
                    code="SLIDE_MISSING_SPTREE",
                    message="Missing p:cSld/p:spTree",
                    locator=part,
                )
            )
            return []
        context = self._resolver.resolve(part, root)
        shapes: list[ShapeBlock] = []
        for child in sp_tree:
            name = local_name(child.tag)
            if name == "sp":
                shape = self._text_shape(child, part, len(shapes) + 1)
            elif name == "pic":
                shape = self._picture_shape(child, part, len(shapes) + 1)
            elif name == "media":
                shape = self._media_shape(child, part, len(shapes) + 1)
            elif name == "graphicFrame":
                shape = self._graphic_frame_shape(child, part, len(shapes) + 1)
            elif name in {"nvGrpSpPr", "grpSpPr"}:
                continue
            else:
                self._warnings.append(
                    ParseWarning(
                        code="UNSUPPORTED_SHAPE_TYPE",
                        message=f"Unsupported shape type: {name}",
                        locator=part,
                    )
                )
                continue
            if shape is not None:
                self._attach_inheritance(shape, child, context)
                shapes.append(shape)
        # Geometric reading order: top→bottom, left→right; stable sort keeps
        # XML order (z-order) for ties; shapes without coordinates sort last.
        shapes.sort(key=self._geometric_key)
        return shapes

    def _attach_inheritance(self, shape: ShapeBlock, element: ET.Element, context: LayoutContext) -> None:
        """Attach placeholder type (own declaration or layout-by-idx) and per-mille coordinates."""
        ph = self._find_descendant(element, "ph")
        idx = ph.get("idx") if ph is not None else None
        if ph is not None and ph.get("type"):
            shape["placeholderType"] = ph.get("type") or ""
        elif idx is not None:
            info = context["placeholders"].get(idx)
            if info is not None and info.get("type"):
                shape["placeholderType"] = info["type"]
        geometry = shape_geometry(element, self._warnings)
        if geometry is None and idx is not None:
            info = context["placeholders"].get(idx)
            if info is not None and all(info.get(key) is not None for key in ("x", "y", "w", "h")):
                geometry = (info["x"], info["y"], info["w"], info["h"])
        if geometry is not None and self._slide_size is not None:
            x, y, w, h = geometry
            shape["x"] = round(x / self._slide_size[0] * 1000)
            shape["y"] = round(y / self._slide_size[1] * 1000)
            shape["w"] = round(w / self._slide_size[0] * 1000)
            shape["h"] = round(h / self._slide_size[1] * 1000)

    @staticmethod
    def _geometric_key(shape: ShapeBlock) -> tuple[int, int]:
        y = shape.get("y")
        x = shape.get("x")
        if y is None or x is None:
            return (2**31, 0)
        return (y, x)

    def _text_shape(self, sp: ET.Element, part: str, ordinal: int) -> ShapeBlock | None:
        text = self._tx_body_text(first_child(sp, "p", "txBody"), part)
        if text is None:
            return None
        return {
            "id": f"s{ordinal}",
            "type": "text",
            "name": self._shape_name(sp) or "",
            "text": text,
        }

    def _picture_shape(self, pic: ET.Element, part: str, ordinal: int) -> ShapeBlock | None:
        blip = self._find_descendant(pic, "blip")
        if blip is None:
            self._warnings.append(ParseWarning(code="PICTURE_MISSING_BLIP", message="p:pic without a:blip", locator=part))
            return None
        rid = attr(blip, "r", "embed") or attr(blip, "r", "link")
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "picture",
            "name": self._shape_name(pic) or "",
        }
        alt = self._shape_alt(pic)
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
            "name": self._shape_name(media) or "",
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
        graphic_data = self._find_descendant(frame, "graphicData")
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
        chart_ref = self._find_descendant(frame, "chart")
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
            "name": self._shape_name(frame) or "",
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
        rel_ids = self._find_descendant(frame, "relIds")
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "smartart",
            "name": self._shape_name(frame) or "",
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
        tbl = self._find_descendant(frame, "tbl")
        if tbl is None:
            self._warnings.append(
                ParseWarning(code="TABLE_MISSING_TBL", message="graphicFrame table without a:tbl", locator=part)
            )
            return None
        rows: list[list[str]] = []
        for child in tbl:
            if local_name(child.tag) != "tr":
                continue
            row: list[str] = []
            for cell in child:
                if local_name(cell.tag) != "tc":
                    continue
                tx_body = first_child(cell, "a", "txBody")
                row.append(self._tx_body_text(tx_body, part) or "")
            rows.append(row)
        return {
            "id": f"s{ordinal}",
            "type": "table",
            "name": self._shape_name(frame) or "",
            "rows": rows,
        }

    def _tx_body_text(self, tx_body: ET.Element | None, part: str) -> str | None:
        if tx_body is None:
            return None
        paragraphs: list[str] = []
        for child in tx_body:
            # bodyPr/lstStyle are formatting infrastructure: skipped silently.
            if local_name(child.tag) == "p":
                text = self._paragraph_text(child, part)
                if text:
                    paragraphs.append(text)
        if not paragraphs:
            return None
        return "\n".join(paragraphs)

    def _paragraph_text(self, p: ET.Element, part: str) -> str:
        parts: list[str] = []
        for child in p:
            name = local_name(child.tag)
            if name == "r":
                t = first_child(child, "a", "t")
                if t is not None and t.text:
                    parts.append(t.text)
            elif name == "br":
                parts.append("\n")
            elif name == "tab":
                parts.append("\t")
            elif name == "fld":
                parts.append(self._paragraph_text(child, part))
            elif name in {"pPr", "endParaRPr"}:
                continue
            else:
                self._warnings.append(
                    ParseWarning(
                        code="UNSUPPORTED_PARAGRAPH_CHILD",
                        message=f"Unsupported paragraph child: {name}",
                        locator=part,
                    )
                )
        return "".join(parts)

    @staticmethod
    def _shape_name(shape: ET.Element) -> str | None:
        c_nv_pr = SlideParser._find_descendant(shape, "cNvPr")
        return c_nv_pr.get("name") if c_nv_pr is not None else None

    @staticmethod
    def _shape_alt(shape: ET.Element) -> str | None:
        c_nv_pr = SlideParser._find_descendant(shape, "cNvPr")
        if c_nv_pr is None:
            return None
        descr = c_nv_pr.get("descr")
        return descr or None

    @staticmethod
    def _find_descendant(element: ET.Element, local: str) -> ET.Element | None:
        for descendant in element.iter():
            if local_name(descendant.tag) == local:
                return descendant
        return None
