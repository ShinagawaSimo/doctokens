"""Slide XML parsing: shape dispatch (text, picture, media)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.chart_ml import CHART_EX_GRAPHIC_DATA_URI
from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.omml_latex import omath_to_latex
from ooxml_llm_core.text_numbering import format_drawingml_autonumber

from ..core.constants import attr, first_child, local_name
from ..core.models import (
    AssetLookup,
    ChartLookup,
    LayoutContext,
    LayoutLookup,
    Paragraph,
    ParagraphStyle,
    Run,
    RunFormat,
    ShapeBlock,
    SlideBackground,
    SmartArtLookup,
    TableCell,
)
from ..ooxml.colors import is_default_text_color, resolve_color_element
from ..ooxml.inheritance import LayoutMasterResolver, shape_geometry
from ..plan import PptxFeature, PptxParsePlan
from .text import DrawingTextParser, HyperlinkLookup


@dataclass(frozen=True)
class _GroupTransform:
    """Affine map from a group's local EMU coordinates to slide coordinates."""

    tx: float = 0.0
    ty: float = 0.0
    sx: float = 1.0
    sy: float = 1.0

    def apply(self, geometry: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x, y, w, h = geometry
        return (
            round(self.tx + self.sx * x),
            round(self.ty + self.sy * y),
            round(self.sx * w),
            round(self.sy * h),
        )

    def compose(self, parent: _GroupTransform) -> _GroupTransform:
        """Return ``parent(local(x))`` for nested groups."""
        return _GroupTransform(
            tx=parent.tx + parent.sx * self.tx,
            ty=parent.ty + parent.sy * self.ty,
            sx=parent.sx * self.sx,
            sy=parent.sy * self.sy,
        )


def _minimal_layout_context() -> LayoutContext:
    """Direct slide declarations used when a plan omits theme/layout work."""
    return {"theme": {}, "placeholders": {}, "color_map": {}, "text_styles": {}}


class SlideParser:
    """Extract shapes once, retaining XML z-order while rendering geometrically."""

    def __init__(
        self,
        warnings: list[ParseWarning],
        asset_lookup: AssetLookup,
        chart_lookup: ChartLookup,
        smartart_lookup: SmartArtLookup,
        layout_lookup: LayoutLookup,
        resolver: LayoutMasterResolver | None,
        slide_size: tuple[int, int] | None,
        theme: dict[str, str],
        hyperlink_lookup: HyperlinkLookup,
        plan: PptxParsePlan | None = None,
    ) -> None:
        self._warnings = warnings
        self._asset_lookup = asset_lookup
        self._chart_lookup = chart_lookup
        self._smartart_lookup = smartart_lookup
        self._layout_lookup = layout_lookup
        self._resolver = resolver
        self._plan = plan or PptxParsePlan.session()
        self._slide_size = slide_size
        self._theme = theme
        self._hyperlink_lookup = hyperlink_lookup
        self._text_parser = DrawingTextParser(
            warnings,
            hyperlink_lookup,
            shape_runs,
            include_formatting=self._plan.needs(PptxFeature.TEXT_FORMATTING),
        )
        self._table_index = 0

    def parse_slide(self, root: ET.Element, part: str) -> tuple[bool, list[ShapeBlock], SlideBackground | None]:
        """Return hidden state, shapes, and the explicit slide background."""
        if local_name(root.tag) != "sld":
            self._warnings.append(
                ParseWarning(
                    code="SLIDE_INVALID_ROOT",
                    message=f"Slide root element is not p:sld: {root.tag}",
                    locator=part,
                )
            )
        hidden = root.get("show") == "0"
        context = self._resolver.resolve(part, root) if self._resolver is not None else _minimal_layout_context()
        background = self._background(root, part, context) if self._plan.needs(PptxFeature.GEOMETRY) else None
        return hidden, self._shapes(root, part, context), background

    def _shapes(self, root: ET.Element, part: str, context: LayoutContext) -> list[ShapeBlock]:
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
        shapes: list[ShapeBlock] = []
        drawing_id_to_shape_id: dict[str, str] = {}
        ordinal = 0
        z_index = 0

        def visit(node: ET.Element, transform: _GroupTransform) -> None:
            nonlocal ordinal, z_index
            name = local_name(node.tag)
            if name in {"nvGrpSpPr", "grpSpPr"}:
                return
            if name == "grpSp":
                group_transform = (
                    self._group_transform(node, transform, part)
                    if self._plan.needs(PptxFeature.GEOMETRY)
                    else transform
                )
                for child in node:
                    visit(child, group_transform)
                return
            z_index += 1
            candidate_ordinal = ordinal + 1
            if name == "sp":
                shape = self._text_shape(node, part, candidate_ordinal, context)
            elif name == "pic":
                shape = self._picture_shape(node, part, candidate_ordinal)
            elif name == "media":
                shape = self._media_shape(node, part, candidate_ordinal)
            elif name == "graphicFrame":
                shape = self._graphic_frame_shape(node, part, candidate_ordinal)
            elif name == "cxnSp":
                shape = self._connector_shape(node, candidate_ordinal)
            else:
                self._warnings.append(
                    ParseWarning(
                        code="UNSUPPORTED_SHAPE_TYPE",
                        message=f"Unsupported shape type: {name}",
                        locator=part,
                    )
                )
                return
            if shape is not None:
                ordinal += 1
                shape["z"] = z_index
                self._attach_inheritance(shape, node, context, transform)
                self._attach_shape_navigation(shape, node, part)
                drawing_id = self._drawing_id(node)
                if drawing_id:
                    drawing_id_to_shape_id[drawing_id] = shape["id"]
                shapes.append(shape)

        for child in sp_tree:
            visit(child, _GroupTransform())
        self._resolve_connector_endpoints(shapes, drawing_id_to_shape_id)
        self._filter_decorative_shapes(shapes)
        if self._plan.needs(PptxFeature.GEOMETRY):
            shapes.sort(key=self._geometric_key)
        self._renumber_shapes(shapes)
        return shapes

    def _background(
        self,
        root: ET.Element,
        part: str,
        context: LayoutContext,
    ) -> SlideBackground | None:
        c_sld = first_child(root, "p", "cSld")
        bg = first_child(c_sld, "p", "bg") if c_sld is not None else None
        if bg is None:
            return None
        background: SlideBackground = {}
        for descendant in bg.iter():
            name = local_name(descendant.tag)
            if name in {"srgbClr", "schemeClr", "sysClr", "prstClr", "hslClr", "scrgbClr"}:
                color = resolve_color_element(
                    descendant,
                    context["theme"],
                    color_map=context["color_map"],
                    warnings=self._warnings,
                    locator=part,
                )
                if color:
                    background["color"] = color
                    break
        blip = self._find_descendant(bg, "blip")
        if blip is not None:
            rid = attr(blip, "r", "embed") or attr(blip, "r", "link")
            if rid:
                asset = self._asset_lookup.get((part, rid))
                if asset is not None:
                    background["assetId"] = asset["id"]
                else:
                    self._warnings.append(
                        ParseWarning(
                            code="BACKGROUND_ASSET_MISSING",
                            message=f"No background image relationship for {rid}",
                            locator=part,
                        )
                    )
        return background or None

    def _attach_inheritance(
        self,
        shape: ShapeBlock,
        element: ET.Element,
        context: LayoutContext,
        transform: _GroupTransform | None = None,
    ) -> None:
        """Attach placeholder type (own declaration or layout-by-idx) and per-mille coordinates."""
        ph = self._find_descendant(element, "ph")
        idx = ph.get("idx", "0") if ph is not None else None
        own_type = ph.get("type") if ph is not None else None
        inherited = None
        if self._plan.needs(PptxFeature.THEME_AND_LAYOUT):
            inherited = context["placeholders"].get(idx or "")
            if inherited is None and own_type:
                inherited = context["placeholders"].get(f"type:{own_type}")
        if ph is not None and ph.get("type"):
            shape["placeholderType"] = ph.get("type") or ""
        elif inherited is not None and inherited.get("type"):
            shape["placeholderType"] = inherited["type"]
        geometry = None
        if self._plan.needs(PptxFeature.GEOMETRY):
            geometry = shape_geometry(element, self._warnings)
            if geometry is None and inherited is not None and all(inherited.get(key) is not None for key in ("x", "y", "w", "h")):
                geometry = (inherited["x"], inherited["y"], inherited["w"], inherited["h"])
            if geometry is not None:
                geometry = (transform or _GroupTransform()).apply(geometry)
        if geometry is not None and self._slide_size is not None:
            x, y, w, h = geometry
            shape["x"] = round(x / self._slide_size[0] * 1000)
            shape["y"] = round(y / self._slide_size[1] * 1000)
            shape["w"] = round(w / self._slide_size[0] * 1000)
            shape["h"] = round(h / self._slide_size[1] * 1000)

    def _attach_shape_navigation(self, shape: ShapeBlock, element: ET.Element, part: str) -> None:
        """Keep click/hover actions attached to a whole shape, separate from run hyperlinks."""
        self._attach_accessibility(shape, element)
        c_nv_pr = self._find_descendant(element, "cNvPr")
        if c_nv_pr is None:
            return
        action = first_child(c_nv_pr, "a", "hlinkClick")
        if action is None:
            action = first_child(c_nv_pr, "a", "hlinkHover")
        if action is None:
            return
        relationship_id = attr(action, "r", "id")
        target = self._hyperlink_lookup.get((part, relationship_id)) if relationship_id else None
        target = target or action.get("action")
        if target:
            shape["link"] = target

    def _text_shape(self, sp: ET.Element, part: str, ordinal: int, context: LayoutContext) -> ShapeBlock | None:
        tx_body = first_child(sp, "p", "txBody")
        text_result = self._text_parser.parse(
            tx_body,
            part=part,
            theme=context["theme"],
            color_map=context["color_map"],
            inherited_styles=(
                self._shape_text_styles(sp, context, part)
                if self._plan.needs(PptxFeature.THEME_AND_LAYOUT)
                else None
            ),
        )
        if text_result.text is None:
            return self._descriptive_shape(sp, ordinal)
        text = text_result.text
        runs = text_result.runs
        paragraphs = text_result.paragraphs
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "text",
            "name": self._shape_name(sp) or "",
            "text": text,
        }
        if runs and any(set(run) != {"text"} for run in runs):
            shape["runs"] = runs
        if paragraphs and any("bullet" in paragraph or "numberType" in paragraph for paragraph in paragraphs):
            shape["paragraphs"] = paragraphs
        return shape

    def _descriptive_shape(self, sp: ET.Element, ordinal: int) -> ShapeBlock:
        """Keep textless shapes only when their accessibility or action data matters."""
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "shape",
            "name": self._shape_name(sp) or "",
            "kind": "shape",
        }
        geometry_type = self._geometry_type(sp)
        if geometry_type:
            shape["geometryType"] = geometry_type
            shape["kind"] = geometry_type
        self._attach_accessibility(shape, sp)
        return shape

    def _connector_shape(self, connector: ET.Element, ordinal: int) -> ShapeBlock:
        """Represent a connector as a semantic edge between retained shapes."""
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "shape",
            "name": self._shape_name(connector) or "",
            "kind": "connector",
        }
        geometry_type = self._geometry_type(connector)
        if geometry_type:
            shape["geometryType"] = geometry_type
        self._attach_accessibility(shape, connector)
        start = self._find_descendant(connector, "stCxn")
        end = self._find_descendant(connector, "endCxn")
        if start is not None and (start_id := start.get("id")):
            shape["fromShape"] = start_id
        if end is not None and (end_id := end.get("id")):
            shape["toShape"] = end_id
        return shape

    @staticmethod
    def _is_meaningful_shape(shape: ShapeBlock) -> bool:
        return bool(shape.get("alt") or shape.get("title") or shape.get("link") or shape.get("fromShape") or shape.get("toShape"))

    @staticmethod
    def _resolve_connector_endpoints(
        shapes: list[ShapeBlock],
        drawing_id_to_shape_id: dict[str, str],
    ) -> None:
        for shape in shapes:
            if shape.get("kind") != "connector":
                continue
            from_drawing_id = shape.get("fromShape")
            if from_drawing_id is not None:
                from_shape_id = drawing_id_to_shape_id.get(from_drawing_id)
                if from_shape_id is None:
                    shape.pop("fromShape", None)
                else:
                    shape["fromShape"] = from_shape_id
            to_drawing_id = shape.get("toShape")
            if to_drawing_id is not None:
                to_shape_id = drawing_id_to_shape_id.get(to_drawing_id)
                if to_shape_id is None:
                    shape.pop("toShape", None)
                else:
                    shape["toShape"] = to_shape_id

    @staticmethod
    def _filter_decorative_shapes(shapes: list[ShapeBlock]) -> None:
        """Keep a connector's endpoints, but omit otherwise inert drawing marks."""
        connector_endpoints = {
            endpoint
            for shape in shapes
            if shape.get("kind") == "connector" and SlideParser._is_meaningful_shape(shape)
            for endpoint in (shape.get("fromShape"), shape.get("toShape"))
            if endpoint is not None
        }
        shapes[:] = [
            shape
            for shape in shapes
            if shape["type"] != "shape" or SlideParser._is_meaningful_shape(shape) or shape["id"] in connector_endpoints
        ]

    @staticmethod
    def _geometric_key(shape: ShapeBlock) -> tuple[int, int]:
        y = shape.get("y")
        x = shape.get("x")
        if y is None or x is None:
            return (2**31, 0)
        return (y, x)

    @staticmethod
    def _renumber_shapes(shapes: list[ShapeBlock]) -> None:
        """Keep compact, contiguous IR IDs after density-driven decoration filtering."""
        replacement_ids = {shape["id"]: f"s{index}" for index, shape in enumerate(shapes, start=1)}
        for shape in shapes:
            shape["id"] = replacement_ids[shape["id"]]
            if from_shape := shape.get("fromShape"):
                shape["fromShape"] = replacement_ids.get(from_shape, from_shape)
            if to_shape := shape.get("toShape"):
                shape["toShape"] = replacement_ids.get(to_shape, to_shape)

    def _shape_text_styles(
        self,
        shape: ET.Element,
        context: LayoutContext,
        part: str,
    ) -> dict[int, ParagraphStyle]:
        ph = self._find_descendant(shape, "ph")
        ph_type = ph.get("type", "obj") if ph is not None else "other"
        idx = ph.get("idx", "0") if ph is not None else None
        role = "title" if ph_type in {"title", "ctrTitle"} else "body" if ph_type in {"body", "subTitle", "obj"} else "other"
        result: dict[int, ParagraphStyle] = {}
        keys = [role, f"type:{ph_type}"]
        if idx is not None:
            keys.append(f"idx:{idx}")
        for key in keys:
            for level, style in context["text_styles"].get(key, {}).items():
                merged = cast(ParagraphStyle, dict(result.get(level, {})))
                if style.get("runFormat"):
                    merged["runFormat"] = {**merged.get("runFormat", {}), **style["runFormat"]}
                for name in ("bullet", "numberType", "startAt"):
                    if name in style:
                        merged[name] = style[name]
                result[level] = merged
        tx_body = first_child(shape, "p", "txBody")
        lst_style = first_child(tx_body, "a", "lstStyle") if tx_body is not None else None
        if lst_style is not None:
            for child in lst_style:
                name = local_name(child.tag)
                if not (name.startswith("lvl") and name.endswith("pPr")):
                    continue
                try:
                    level = max(0, int(name[3:-3]) - 1)
                except ValueError:
                    continue
                style = cast(ParagraphStyle, dict(result.get(level, {})))
                bullet = first_child(child, "a", "buChar")
                auto = first_child(child, "a", "buAutoNum")
                if first_child(child, "a", "buNone") is not None:
                    style.pop("bullet", None)
                    style.pop("numberType", None)
                elif bullet is not None and bullet.get("char"):
                    style["bullet"] = bullet.get("char", "")
                    style.pop("numberType", None)
                elif auto is not None:
                    style["numberType"] = auto.get("type", "arabicPeriod")
                    style["startAt"] = _parse_int(auto.get("startAt"), 1)
                    style.pop("bullet", None)
                def_r_pr = first_child(child, "a", "defRPr")
                if def_r_pr is not None:
                    style["runFormat"] = {
                        **style.get("runFormat", {}),
                        **_format_properties(
                            def_r_pr,
                            context["theme"],
                            context["color_map"],
                            self._warnings,
                            part,
                        ),
                    }
                result[level] = style
        return result

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

    def _group_transform(
        self,
        group: ET.Element,
        parent: _GroupTransform,
        part: str,
    ) -> _GroupTransform:
        grp_pr = first_child(group, "p", "grpSpPr")
        xfrm = first_child(grp_pr, "a", "xfrm") if grp_pr is not None else None
        if xfrm is None:
            return parent
        off = first_child(xfrm, "a", "off")
        ext = first_child(xfrm, "a", "ext")
        ch_off = first_child(xfrm, "a", "chOff")
        ch_ext = first_child(xfrm, "a", "chExt")
        try:
            ox = int(off.get("x", "0")) if off is not None else 0
            oy = int(off.get("y", "0")) if off is not None else 0
            ex = int(ext.get("cx", "0")) if ext is not None else 0
            ey = int(ext.get("cy", "0")) if ext is not None else 0
            cx = int(ch_off.get("x", "0")) if ch_off is not None else 0
            cy = int(ch_off.get("y", "0")) if ch_off is not None else 0
            cex = int(ch_ext.get("cx", "0")) if ch_ext is not None else 0
            cey = int(ch_ext.get("cy", "0")) if ch_ext is not None else 0
            if cex == 0 or cey == 0:
                raise ValueError("group child extent is zero")
            local = _GroupTransform(ox - cx * ex / cex, oy - cy * ey / cey, ex / cex, ey / cey)
            return local.compose(parent)
        except (TypeError, ValueError):
            self._warnings.append(
                ParseWarning(code="GROUP_GEOMETRY_INVALID", message="Invalid group coordinate transform", locator=part)
            )
            return parent

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
            "name": self._shape_name(frame) or "",
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
        title = c_nv_pr.get("title")
        return descr or title or None

    @staticmethod
    def _geometry_type(shape: ET.Element) -> str | None:
        geometry = SlideParser._find_descendant(shape, "prstGeom")
        return geometry.get("prst") if geometry is not None else None

    @staticmethod
    def _drawing_id(shape: ET.Element) -> str | None:
        c_nv_pr = SlideParser._find_descendant(shape, "cNvPr")
        return c_nv_pr.get("id") if c_nv_pr is not None else None

    def _attach_accessibility(self, result: ShapeBlock, shape: ET.Element) -> None:
        c_nv_pr = self._find_descendant(shape, "cNvPr")
        if c_nv_pr is None:
            return
        if description := c_nv_pr.get("descr"):
            result["alt"] = description
        if title := c_nv_pr.get("title"):
            result["title"] = title

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
    counters: dict[tuple[str, int], int] = {}
    for child in tx_body:
        # bodyPr/lstStyle are formatting infrastructure: skipped silently.
        if local_name(child.tag) == "p":
            text = paragraph_text(child, part, warnings, counters)
            if text:
                paragraphs.append(text)
    if not paragraphs:
        return None
    return "\n".join(paragraphs)


def paragraph_text(
    p: ET.Element,
    part: str,
    warnings: list[ParseWarning],
    counters: dict[tuple[str, int], int] | None = None,
) -> str:
    """Flatten a paragraph's runs/breaks/tabs/fields into plain text."""
    runs = paragraph_runs(p, part, warnings, {}, {}, {})
    prefix = _list_prefix(p, counters if counters is not None else {})
    return prefix + "".join(run.get("text", "") for run in runs)


def shape_runs(
    tx_body: ET.Element | None,
    part: str,
    warnings: list[ParseWarning],
    theme: dict[str, str],
    color_map: dict[str, str],
    links: HyperlinkLookup,
    inherited_styles: dict[int, ParagraphStyle] | None = None,
    paragraphs_out: list[Paragraph] | None = None,
    include_formatting: bool = True,
) -> list[Run]:
    """Run-level IR for a txBody: paragraphs joined by synthetic newline runs."""
    if tx_body is None:
        return []
    runs: list[Run] = []
    counters: dict[tuple[str, int], int] = {}
    for child in tx_body:
        if local_name(child.tag) != "p":
            continue
        p_pr = first_child(child, "a", "pPr")
        level = _parse_int(p_pr.get("lvl") if p_pr is not None else None, 0)
        style = (inherited_styles or {}).get(level, (inherited_styles or {}).get(0, {}))
        base_format = cast(RunFormat, dict(style.get("runFormat", {}))) if include_formatting else {}
        if include_formatting and p_pr is not None:
            def_r_pr = first_child(p_pr, "a", "defRPr")
            if def_r_pr is not None:
                base_format.update(_format_properties(def_r_pr, theme, color_map, warnings, part))
        paragraph = paragraph_runs(
            child,
            part,
            warnings,
            theme,
            color_map,
            links,
            base_format,
            include_formatting=include_formatting,
        )
        prefix = _list_prefix(child, counters, style)
        if prefix:
            paragraph.insert(0, {"text": prefix})
        if paragraph:
            if paragraphs_out is not None:
                metadata: Paragraph = {
                    "text": "".join(run.get("text", "") for run in paragraph),
                    "level": level,
                }
                metadata.update(_list_metadata(child, style))
                paragraphs_out.append(metadata)
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
    base_format: RunFormat | None = None,
    *,
    include_formatting: bool = True,
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
            run_format = cast(RunFormat, dict(base_format or {})) if include_formatting else {}
            if include_formatting:
                run_format.update(_run_format(child, theme, color_map, warnings, part))
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
            runs.extend(
                paragraph_runs(
                    child,
                    part,
                    warnings,
                    theme,
                    color_map,
                    links,
                    base_format,
                    include_formatting=include_formatting,
                )
            )
        elif name in {"pPr", "endParaRPr"}:
            continue
        elif name in {"oMath", "oMathPara"}:
            latex = omath_to_latex(child)
            if latex:
                runs.append({"text": latex, "equation": latex})
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


def _list_prefix(
    p: ET.Element,
    counters: dict[tuple[str, int], int],
    inherited: ParagraphStyle | None = None,
) -> str:
    """Return the visible bullet/number prefix for a paragraph."""
    p_pr = first_child(p, "a", "pPr")
    level = _parse_int(p_pr.get("lvl") if p_pr is not None else None, 0)
    if p_pr is not None and first_child(p_pr, "a", "buNone") is not None:
        return ""
    bullet = first_child(p_pr, "a", "buChar") if p_pr is not None else None
    if bullet is not None:
        return (bullet.get("char") or "•") + " "
    auto = first_child(p_pr, "a", "buAutoNum") if p_pr is not None else None
    inherited = inherited or {}
    if auto is None and inherited.get("bullet"):
        return inherited["bullet"] + " "
    if auto is None and not inherited.get("numberType"):
        return ""
    number_type = auto.get("type", "arabicPeriod") if auto is not None else inherited["numberType"]
    key = (number_type, level)
    start = _parse_int(auto.get("startAt") if auto is not None else None, inherited.get("startAt", 1))
    if key not in counters:
        counters[key] = start
    else:
        counters[key] += 1
    return f"{_format_list_number(counters[key], number_type)} "


def _list_metadata(p: ET.Element, inherited: ParagraphStyle) -> Paragraph:
    result: Paragraph = {}
    p_pr = first_child(p, "a", "pPr")
    if p_pr is not None and first_child(p_pr, "a", "buNone") is not None:
        return result
    bullet = first_child(p_pr, "a", "buChar") if p_pr is not None else None
    auto = first_child(p_pr, "a", "buAutoNum") if p_pr is not None else None
    if bullet is not None:
        result["bullet"] = bullet.get("char") or "•"
    elif auto is not None:
        result["numberType"] = auto.get("type", "arabicPeriod")
        result["startAt"] = _parse_int(auto.get("startAt"), 1)
    elif inherited.get("bullet"):
        result["bullet"] = inherited["bullet"]
    elif inherited.get("numberType"):
        result["numberType"] = inherited["numberType"]
        result["startAt"] = inherited.get("startAt", 1)
    return result


def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _format_list_number(number: int, number_type: str) -> str:
    return format_drawingml_autonumber(number, number_type)


def _run_format(
    r: ET.Element,
    theme: dict[str, str],
    color_map: dict[str, str],
    warnings: list[ParseWarning],
    part: str,
) -> RunFormat:
    r_pr = first_child(r, "a", "rPr")
    if r_pr is None:
        return {}
    return _format_properties(r_pr, theme, color_map, warnings, part)


def _format_properties(
    r_pr: ET.Element,
    theme: dict[str, str],
    color_map: dict[str, str],
    warnings: list[ParseWarning],
    part: str,
) -> RunFormat:
    fmt: RunFormat = {}
    if r_pr.get("b") is not None:
        fmt["bold"] = _drawingml_bool(r_pr.get("b"))
    elif first_child(r_pr, "a", "b") is not None:
        fmt["bold"] = True
    if r_pr.get("i") is not None:
        fmt["italic"] = _drawingml_bool(r_pr.get("i"))
    elif first_child(r_pr, "a", "i") is not None:
        fmt["italic"] = True
    underline_value = r_pr.get("u")
    underline = first_child(r_pr, "a", "u")
    if underline_value is not None:
        fmt["underline"] = underline_value not in {"none", "0", "false", "off"}
    elif underline is not None:
        fmt["underline"] = underline.get("val", "") not in {"none", "0", "false", "off"}
    solid_fill = first_child(r_pr, "a", "solidFill")
    if solid_fill is not None:
        for color_element in solid_fill:
            color = resolve_color_element(
                color_element,
                theme,
                color_map=color_map,
                warnings=warnings,
                locator=part,
            )
            if color and not is_default_text_color(color):
                fmt["color"] = color
                break
    return fmt


def _drawingml_bool(value: str | None) -> bool:
    return value is not None and value.lower() not in {"0", "false", "off", "no"}


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
