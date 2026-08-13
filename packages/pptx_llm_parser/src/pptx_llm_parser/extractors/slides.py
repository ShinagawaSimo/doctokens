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
    Run,
    RunFormat,
    ShapeBlock,
    SmartArtLookup,
)
from ..ooxml.colors import is_default_text_color, resolve_color_element
from ..ooxml.inheritance import LayoutMasterResolver, shape_geometry

HyperlinkLookup = dict[tuple[str, str], str]


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
        theme: dict[str, str],
        hyperlink_lookup: HyperlinkLookup,
    ) -> None:
        self._warnings = warnings
        self._asset_lookup = asset_lookup
        self._chart_lookup = chart_lookup
        self._smartart_lookup = smartart_lookup
        self._layout_lookup = layout_lookup
        self._resolver = resolver
        self._slide_size = slide_size
        self._theme = theme
        self._hyperlink_lookup = hyperlink_lookup
        self._table_index = 0

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
        z_index = 0
        for child in sp_tree:
            name = local_name(child.tag)
            if name in {"nvGrpSpPr", "grpSpPr"}:
                continue
            z_index += 1
            if name == "sp":
                shape = self._text_shape(child, part, len(shapes) + 1, context)
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
                shape["z"] = z_index
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

    def _text_shape(self, sp: ET.Element, part: str, ordinal: int, context: LayoutContext) -> ShapeBlock | None:
        tx_body = first_child(sp, "p", "txBody")
        text = tx_body_text(tx_body, part, self._warnings)
        if text is None:
            return None
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "text",
            "name": self._shape_name(sp) or "",
            "text": text,
        }
        runs = shape_runs(
            tx_body,
            part,
            self._warnings,
            self._theme,
            context["color_map"],
            self._hyperlink_lookup,
        )
        if runs and any(set(run) != {"text"} for run in runs):
            shape["runs"] = runs
        return shape

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
                row.append(tx_body_text(tx_body, part, self._warnings) or "")
            rows.append(row)
        self._table_index += 1
        return {
            "id": f"s{ordinal}",
            "type": "table",
            "name": self._shape_name(frame) or "",
            "rows": rows,
            "tableId": f"table{self._table_index}",
        }

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


def tx_body_text(tx_body: ET.Element | None, part: str, warnings: list[ParseWarning]) -> str | None:
    """Join a txBody's paragraphs into one text block (paragraphs by \\n)."""
    if tx_body is None:
        return None
    paragraphs: list[str] = []
    for child in tx_body:
        # bodyPr/lstStyle are formatting infrastructure: skipped silently.
        if local_name(child.tag) == "p":
            text = paragraph_text(child, part, warnings)
            if text:
                paragraphs.append(text)
    if not paragraphs:
        return None
    return "\n".join(paragraphs)


def paragraph_text(p: ET.Element, part: str, warnings: list[ParseWarning]) -> str:
    """Flatten a paragraph's runs/breaks/tabs/fields into plain text."""
    return "".join(run["text"] for run in paragraph_runs(p, part, warnings, {}, {}, {}))


def shape_runs(
    tx_body: ET.Element | None,
    part: str,
    warnings: list[ParseWarning],
    theme: dict[str, str],
    color_map: dict[str, str],
    links: HyperlinkLookup,
) -> list[Run]:
    """Run-level IR for a txBody: paragraphs joined by synthetic newline runs."""
    if tx_body is None:
        return []
    runs: list[Run] = []
    for child in tx_body:
        if local_name(child.tag) != "p":
            continue
        paragraph = paragraph_runs(child, part, warnings, theme, color_map, links)
        if paragraph:
            if runs:
                runs.append({"text": "\n"})
            runs.extend(paragraph)
    return runs


def paragraph_runs(
    p: ET.Element,
    part: str,
    warnings: list[ParseWarning],
    theme: dict[str, str],
    color_map: dict[str, str],
    links: HyperlinkLookup,
) -> list[Run]:
    """Per-run extraction with rPr formats, hyperlinks, breaks, tabs, fields."""
    runs: list[Run] = []
    pending = ""
    for child in p:
        name = local_name(child.tag)
        if name == "r":
            if pending:
                runs.append({"text": pending})
                pending = ""
            text = _run_text(child)
            run: Run = {}
            if text:
                run["text"] = text
            run_format = _run_format(child, theme, color_map)
            if run_format:
                run["format"] = run_format
            link = _run_link(child, links, part)
            if link:
                run["link"] = link
            if run:
                runs.append(run)
        elif name == "br":
            pending += "\n"
        elif name == "tab":
            pending += "\t"
        elif name == "fld":
            if pending:
                runs.append({"text": pending})
                pending = ""
            runs.extend(paragraph_runs(child, part, warnings, theme, color_map, links))
        elif name in {"pPr", "endParaRPr"}:
            continue
        else:
            warnings.append(
                ParseWarning(
                    code="UNSUPPORTED_PARAGRAPH_CHILD",
                    message=f"Unsupported paragraph child: {name}",
                    locator=part,
                )
            )
    if pending:
        runs.append({"text": pending})
    return runs


def _run_text(r: ET.Element) -> str:
    t = first_child(r, "a", "t")
    return t.text if t is not None and t.text else ""


def _run_format(r: ET.Element, theme: dict[str, str], color_map: dict[str, str]) -> RunFormat:
    r_pr = first_child(r, "a", "rPr")
    if r_pr is None:
        return {}
    fmt: RunFormat = {}
    if first_child(r_pr, "a", "b") is not None:
        fmt["bold"] = True
    if first_child(r_pr, "a", "i") is not None:
        fmt["italic"] = True
    underline = first_child(r_pr, "a", "u")
    if underline is not None and underline.get("val", "") not in {"none", "0"}:
        fmt["underline"] = True
    solid_fill = first_child(r_pr, "a", "solidFill")
    if solid_fill is not None:
        for color_element in solid_fill:
            color = resolve_color_element(color_element, theme, color_map=color_map)
            if color and not is_default_text_color(color):
                fmt["color"] = color
                break
    return fmt


def _run_link(r: ET.Element, links: HyperlinkLookup, part: str) -> str | None:
    r_pr = first_child(r, "a", "rPr")
    if r_pr is None:
        return None
    hlink = first_child(r_pr, "a", "hlinkClick")
    if hlink is None:
        return None
    rid = attr(hlink, "r", "id")
    if rid is not None:
        return links.get((part, rid))
    return hlink.get("action")
