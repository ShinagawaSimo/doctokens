"""Slide XML parsing: shape dispatch (text, picture, media)."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning

from ....core.constants import attr, first_child, local_name
from ....core.models import (
    AssetLookup,
    ChartLookup,
    LayoutContext,
    LayoutLookup,
    ParagraphStyle,
    ShapeBlock,
    SlideBackground,
    SmartArtLookup,
)
from ....ooxml.inheritance import LayoutMasterResolver
from ....plan import PptxFeature, PptxParsePlan
from .geometry import SlideGeometry, _GroupTransform
from .objects import SlideObjectParser
from .runs import _format_properties, _parse_int, shape_runs
from .shape_details import (
    _attach_accessibility,
    _drawing_id,
    _filter_decorative_shapes,
    _find_descendant,
    _geometric_key,
    _geometry_type,
    _renumber_shapes,
    _resolve_connector_endpoints,
    _shape_name,
)
from .text import DrawingTextParser, HyperlinkLookup


def _minimal_layout_context() -> LayoutContext:
    """Direct slide declarations used when a plan omits theme/layout work."""
    return {"theme": {}, "placeholders": {}, "color_map": {}, "text_styles": {}}


class SlideParser:
    """Extract shapes in source order unless a geometry-enabled plan requests sorting."""

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
        self.include_navigation = self._plan.needs(PptxFeature.NAVIGATION)
        self.include_geometry = self._plan.needs(PptxFeature.GEOMETRY)
        self.include_theme_layout = self._plan.needs(PptxFeature.THEME_AND_LAYOUT)
        self.include_formatting = self._plan.needs(PptxFeature.TEXT_FORMATTING)
        self._geometry = SlideGeometry(
            warnings,
            asset_lookup,
            slide_size,
            include_geometry=self.include_geometry,
            include_theme_layout=self.include_theme_layout,
        )
        self._theme = theme
        self._hyperlink_lookup = hyperlink_lookup
        self._text_parser = DrawingTextParser(
            warnings,
            hyperlink_lookup,
            shape_runs,
            include_formatting=self.include_formatting,
        )
        self._objects = SlideObjectParser(warnings, asset_lookup, chart_lookup, smartart_lookup, layout_lookup)

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
        background = self._geometry._background(root, part, context) if self.include_geometry else None
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
                group_transform = self._geometry._group_transform(node, transform, part) if self.include_geometry else transform
                for child in node:
                    visit(child, group_transform)
                return
            z_index += 1
            candidate_ordinal = ordinal + 1
            if name == "sp":
                shape = self._text_shape(node, part, candidate_ordinal, context)
            elif name == "pic":
                shape = self._objects._picture_shape(node, part, candidate_ordinal)
            elif name == "media":
                shape = self._objects._media_shape(node, part, candidate_ordinal)
            elif name == "graphicFrame":
                shape = self._objects._graphic_frame_shape(node, part, candidate_ordinal)
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
            if shape is None:
                return
            ordinal += 1
            shape["z"] = z_index
            self._geometry._attach_inheritance(shape, node, context, transform)
            if self.include_navigation:
                self._attach_shape_navigation(shape, node, part)
            drawing_id = _drawing_id(node)
            if drawing_id:
                drawing_id_to_shape_id[drawing_id] = shape["id"]
            shapes.append(shape)

        for child in sp_tree:
            visit(child, _GroupTransform())
        _resolve_connector_endpoints(shapes, drawing_id_to_shape_id)
        _filter_decorative_shapes(shapes)
        if self.include_geometry:
            shapes.sort(key=_geometric_key)
        _renumber_shapes(shapes)
        return shapes

    def _attach_shape_navigation(self, shape: ShapeBlock, element: ET.Element, part: str) -> None:
        """Keep click/hover actions attached to a whole shape, separate from run hyperlinks."""
        _attach_accessibility(shape, element)
        c_nv_pr = _find_descendant(element, "cNvPr")
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
            inherited_styles=(self._shape_text_styles(sp, context, part) if self.include_theme_layout else None),
        )
        if text_result.text is None:
            return self._descriptive_shape(sp, ordinal)
        text = text_result.text
        runs = text_result.runs
        paragraphs = text_result.paragraphs
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "text",
            "name": _shape_name(sp) or "",
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
            "name": _shape_name(sp) or "",
            "kind": "shape",
        }
        geometry_type = _geometry_type(sp)
        if geometry_type:
            shape["geometryType"] = geometry_type
            shape["kind"] = geometry_type
        _attach_accessibility(shape, sp)
        return shape

    def _connector_shape(self, connector: ET.Element, ordinal: int) -> ShapeBlock:
        """Represent a connector as a semantic edge between retained shapes."""
        shape: ShapeBlock = {
            "id": f"s{ordinal}",
            "type": "shape",
            "name": _shape_name(connector) or "",
            "kind": "connector",
        }
        geometry_type = _geometry_type(connector)
        if geometry_type:
            shape["geometryType"] = geometry_type
        _attach_accessibility(shape, connector)
        start = _find_descendant(connector, "stCxn")
        end = _find_descendant(connector, "endCxn")
        if start is not None and (start_id := start.get("id")):
            shape["fromShape"] = start_id
        if end is not None and (end_id := end.get("id")):
            shape["toShape"] = end_id
        return shape

    def _shape_text_styles(
        self,
        shape: ET.Element,
        context: LayoutContext,
        part: str,
    ) -> dict[int, ParagraphStyle]:
        ph = _find_descendant(shape, "ph")
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
