"""Slide → layout → master inheritance resolution.

Resolves placeholder declarations (idx-matched, geometry inherited through
layout then master by type) and the three-level clrMap merge. Layout/master
text is never read — template prompt text stays out of slide content.
"""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.relationships import RelationshipIndex

from ..core.constants import first_child, local_name
from ..core.models import LayoutContext, ParagraphStyle, PlaceholderInfo, RunFormat
from ..core.package import PackageReader
from .colors import DEFAULT_COLOR_MAP, is_default_text_color, resolve_color_element

SLIDE_LAYOUT_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
SLIDE_MASTER_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"

_CLR_MAP_ATTRS = (
    "tx1",
    "tx2",
    "bg1",
    "bg2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
)


def _read_color_map_attrs(element: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in _CLR_MAP_ATTRS:
        value = element.get(name)
        if value is not None:
            result[name] = value
    return result


def shape_geometry(shape: ET.Element, warnings: list[ParseWarning]) -> tuple[int, int, int, int] | None:
    """Read a shape's a:xfrm off/ext (EMU), or None when absent/invalid."""
    xfrm = None
    for descendant in shape.iter():
        if local_name(descendant.tag) == "xfrm":
            xfrm = descendant
            break
    if xfrm is None:
        return None
    off = first_child(xfrm, "a", "off")
    ext = first_child(xfrm, "a", "ext")
    if off is None or ext is None:
        return None
    try:
        return int(off.get("x", "")), int(off.get("y", "")), int(ext.get("cx", "")), int(ext.get("cy", ""))
    except ValueError:
        warnings.append(
            ParseWarning(
                code="GEOMETRY_INVALID",
                message="Invalid a:xfrm dimensions",
                locator=None,
            )
        )
        return None


class LayoutMasterResolver:
    """Resolve per-slide layout context, cached per slide part."""

    def __init__(
        self,
        pkg: PackageReader,
        relationships: RelationshipIndex,
        warnings: list[ParseWarning],
        theme: dict[str, str] | None = None,
    ) -> None:
        self._pkg = pkg
        self._relationships = relationships
        self._warnings = warnings
        self._theme = theme or {}
        self._cache: dict[str, LayoutContext] = {}

    def resolve(self, slide_part: str, slide_root: ET.Element) -> LayoutContext:
        base = self._cache.get(slide_part)
        if base is None:
            base = self._build(slide_part)
            self._cache[slide_part] = base
        slide_map = self._clr_map_from(slide_root, override=True) or self._clr_map_from(slide_root, override=False)
        # A slide-level override must not leak into another invocation of the
        # same resolver (or into a slide that happens to reuse the cache key).
        return {
            "placeholders": base["placeholders"],
            "color_map": {**base["color_map"], **slide_map},
            "text_styles": base["text_styles"],
        }

    def _build(self, slide_part: str) -> LayoutContext:
        layout_part = self._target_for(slide_part, SLIDE_LAYOUT_REL_TYPE)
        if layout_part is None or not self._pkg.exists(layout_part):
            self._warnings.append(
                ParseWarning(
                    code="LAYOUT_PART_MISSING",
                    message=f"Slide layout part missing: {layout_part}",
                    locator=slide_part,
                )
            )
            return {"placeholders": {}, "color_map": dict(DEFAULT_COLOR_MAP), "text_styles": {}}

        try:
            layout_root = self._read_xml(layout_part)
        except ET.ParseError as exc:
            self._warnings.append(
                ParseWarning(code="LAYOUT_XML_INVALID", message=f"Invalid slide layout XML: {exc}", locator=layout_part)
            )
            return {"placeholders": {}, "color_map": dict(DEFAULT_COLOR_MAP), "text_styles": {}}
        master_part = self._target_for(layout_part, SLIDE_MASTER_REL_TYPE)
        master_by_type: dict[str, tuple[int, int, int, int]] = {}
        master_styles: dict[str, dict[int, ParagraphStyle]] = {}
        if master_part is not None and self._pkg.exists(master_part):
            try:
                master_root = self._read_xml(master_part)
                master_by_type = self._master_geometries(master_root)
                master_map = self._clr_map_from(master_root, override=False)
                master_styles = self._text_styles(master_root, {**DEFAULT_COLOR_MAP, **master_map})
            except ET.ParseError as exc:
                self._warnings.append(
                    ParseWarning(code="MASTER_XML_INVALID", message=f"Invalid slide master XML: {exc}", locator=master_part)
                )
                master_map = {}
        else:
            self._warnings.append(
                ParseWarning(
                    code="MASTER_PART_MISSING",
                    message=f"Slide master part missing: {master_part}",
                    locator=layout_part,
                )
            )
            master_map = {}

        placeholders: dict[str, PlaceholderInfo] = {}
        for shape in self._layout_shapes(layout_root):
            ph = self._find_descendant(shape, "ph")
            if ph is None:
                continue
            idx = ph.get("idx", "0")
            ph_type = ph.get("type", "obj")
            info: PlaceholderInfo = {}
            if ph_type:
                info["type"] = ph_type
            geometry = shape_geometry(shape, self._warnings)
            if geometry is None and ph_type:
                geometry = master_by_type.get(ph_type)
            if geometry is not None:
                x, y, w, h = geometry
                info["x"] = x
                info["y"] = y
                info["w"] = w
                info["h"] = h
            placeholders[idx] = info
            placeholders.setdefault(f"type:{ph_type}", info)

        color_map = {**DEFAULT_COLOR_MAP, **master_map, **self._clr_map_from(layout_root, override=False)}
        layout_styles = self._text_styles(layout_root, color_map)
        return {
            "placeholders": placeholders,
            "color_map": color_map,
            "text_styles": self._merge_text_styles(master_styles, layout_styles),
        }

    def _text_styles(
        self,
        root: ET.Element,
        color_map: dict[str, str],
    ) -> dict[str, dict[int, ParagraphStyle]]:
        result: dict[str, dict[int, ParagraphStyle]] = {}
        tx_styles = self._find_descendant(root, "txStyles")
        if tx_styles is not None:
            role_names = {"titleStyle": "title", "bodyStyle": "body", "otherStyle": "other"}
            for child in tx_styles:
                role = role_names.get(local_name(child.tag))
                if role:
                    result[role] = self._styles_from_container(child, color_map)
        for shape in self._layout_shapes(root):
            ph = self._find_descendant(shape, "ph")
            tx_body = first_child(shape, "p", "txBody")
            lst_style = first_child(tx_body, "a", "lstStyle") if tx_body is not None else None
            if ph is None or lst_style is None:
                continue
            styles = self._styles_from_container(lst_style, color_map)
            if not styles:
                continue
            result[f"idx:{ph.get('idx', '0')}"] = styles
            result[f"type:{ph.get('type', 'obj')}"] = styles
        return result

    def _styles_from_container(
        self,
        container: ET.Element,
        color_map: dict[str, str],
    ) -> dict[int, ParagraphStyle]:
        result: dict[int, ParagraphStyle] = {}
        for child in container:
            name = local_name(child.tag)
            if name == "defPPr":
                level = 0
            elif name.startswith("lvl") and name.endswith("pPr"):
                try:
                    level = max(0, int(name[3:-3]) - 1)
                except ValueError:
                    continue
            else:
                continue
            style: ParagraphStyle = {}
            bullet = first_child(child, "a", "buChar")
            auto = first_child(child, "a", "buAutoNum")
            if bullet is not None and bullet.get("char"):
                style["bullet"] = bullet.get("char", "")
            elif auto is not None:
                style["numberType"] = auto.get("type", "arabicPeriod")
                try:
                    style["startAt"] = int(auto.get("startAt", "1"))
                except ValueError:
                    style["startAt"] = 1
            def_r_pr = first_child(child, "a", "defRPr")
            if def_r_pr is not None:
                run_format = self._run_defaults(def_r_pr, color_map)
                if run_format:
                    style["runFormat"] = run_format
            if style:
                result[level] = style
        return result

    def _run_defaults(self, r_pr: ET.Element, color_map: dict[str, str]) -> RunFormat:
        result: RunFormat = {}
        for attribute, key in (("b", "bold"), ("i", "italic")):
            value = r_pr.get(attribute)
            if value is not None:
                result[key] = value.lower() not in {"0", "false", "off", "no"}  # type: ignore[literal-required]
        underline = r_pr.get("u")
        if underline is not None:
            result["underline"] = underline not in {"none", "0", "false", "off"}
        solid_fill = first_child(r_pr, "a", "solidFill")
        if solid_fill is not None:
            for color_element in solid_fill:
                color = resolve_color_element(
                    color_element,
                    self._theme,
                    color_map=color_map,
                    warnings=self._warnings,
                )
                if color and not is_default_text_color(color):
                    result["color"] = color
                    break
        return result

    @staticmethod
    def _merge_text_styles(
        base: dict[str, dict[int, ParagraphStyle]],
        overlay: dict[str, dict[int, ParagraphStyle]],
    ) -> dict[str, dict[int, ParagraphStyle]]:
        result: dict[str, dict[int, ParagraphStyle]] = {
            key: {level: cast(ParagraphStyle, dict(style)) for level, style in levels.items()} for key, levels in base.items()
        }
        for key, levels in overlay.items():
            target = result.setdefault(key, {})
            for level, style in levels.items():
                merged = cast(ParagraphStyle, dict(target.get(level, {})))
                if "runFormat" in style:
                    merged["runFormat"] = {**merged.get("runFormat", {}), **style["runFormat"]}
                for name in ("bullet", "numberType", "startAt"):
                    if name in style:
                        merged[name] = style[name]
                target[level] = merged
        return result

    def _layout_shapes(self, layout_root: ET.Element) -> list[ET.Element]:
        c_sld = first_child(layout_root, "p", "cSld")
        sp_tree = first_child(c_sld, "p", "spTree") if c_sld is not None else None
        if sp_tree is None:
            return []
        return [child for child in sp_tree if local_name(child.tag) == "sp"]

    def _master_geometries(self, master_root: ET.Element) -> dict[str, tuple[int, int, int, int]]:
        geometries: dict[str, tuple[int, int, int, int]] = {}
        for shape in self._layout_shapes(master_root):
            ph = self._find_descendant(shape, "ph")
            if ph is None:
                continue
            ph_type = ph.get("type", "obj")
            geometry = shape_geometry(shape, self._warnings)
            if ph_type and geometry is not None:
                geometries[ph_type] = geometry
        return geometries

    def _clr_map_from(self, root: ET.Element, *, override: bool) -> dict[str, str]:
        if override:
            ovr = first_child(root, "p", "clrMapOvr")
            if ovr is not None:
                mapping_el = first_child(ovr, "a", "overrideClrMapping")
                if mapping_el is None:
                    mapping_el = first_child(ovr, "a", "masterClrMapping")
                if mapping_el is not None:
                    return _read_color_map_attrs(mapping_el)
        node = first_child(root, "p", "clrMap")
        if node is None:
            return {}
        return _read_color_map_attrs(node)

    def _target_for(self, source_part: str, rel_type: str) -> str | None:
        for record in self._relationships.by_source(source_part):
            if record.type == rel_type:
                return record.resolved_target
        return None

    def _read_xml(self, part: str) -> ET.Element:
        with self._pkg.open_entry(part) as stream:
            return ET.parse(stream).getroot()

    @staticmethod
    def _find_descendant(element: ET.Element, local: str) -> ET.Element | None:
        for descendant in element.iter():
            if local_name(descendant.tag) == local:
                return descendant
        return None
