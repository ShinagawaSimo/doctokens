"""Slide → layout → master inheritance resolution.

Resolves placeholder declarations (idx-matched, geometry inherited through
layout then master by type) and the three-level clrMap merge. Layout/master
text is never read — template prompt text stays out of slide content.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.relationships import RelationshipIndex

from ..core.constants import first_child, local_name
from ..core.models import LayoutContext, ParagraphStyle, PlaceholderInfo
from ..core.package import PackageReader
from .colors import DEFAULT_COLOR_MAP
from .text_styles import TextStyleParser, _find_descendant, _layout_shapes, _merge_text_styles
from .theme import ThemeParser

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


@dataclass(frozen=True, slots=True)
class _TemplateModel:
    """Parsed layout/master products shared by every slide using that part."""

    part: str
    theme: dict[str, str]
    placeholders: dict[str, PlaceholderInfo]
    color_map: dict[str, str]
    text_styles: dict[str, dict[int, ParagraphStyle]]


class LayoutMasterResolver:
    """Resolve per-slide layout context with slide and template-level caches."""

    def __init__(
        self,
        pkg: PackageReader,
        relationships: RelationshipIndex,
        warnings: list[ParseWarning],
        theme: dict[str, str] | None = None,
        theme_parser: ThemeParser | None = None,
    ) -> None:
        self._pkg = pkg
        self._relationships = relationships
        self._warnings = warnings
        self._theme = theme or {}
        self._text_styles = TextStyleParser(self._theme, warnings)
        self._theme_parser = theme_parser
        self._cache: dict[str, LayoutContext] = {}
        self._layout_cache: dict[str, _TemplateModel] = {}
        self._master_cache: dict[str, _TemplateModel] = {}
        self._target_cache: dict[tuple[str, str], str | None] = {}

    def resolve(self, slide_part: str, slide_root: ET.Element) -> LayoutContext:
        base = self._cache.get(slide_part)
        if base is None:
            base = self._build(slide_part)
            self._cache[slide_part] = base
        slide_map = self._clr_map_from(slide_root, override=True) or self._clr_map_from(slide_root, override=False)
        # A slide-level override must not leak into another invocation of the
        # same resolver (or into a slide that happens to reuse the cache key).
        return {
            "theme": base["theme"],
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
            return self._empty_context()
        return self._layout_model(layout_part)

    def _empty_context(self) -> LayoutContext:
        return {
            "theme": dict(self._theme),
            "placeholders": {},
            "color_map": dict(DEFAULT_COLOR_MAP),
            "text_styles": {},
        }

    def _layout_model(self, layout_part: str) -> LayoutContext:
        cached = self._layout_cache.get(layout_part)
        if cached is not None:
            return {
                "theme": cached.theme,
                "placeholders": cached.placeholders,
                "color_map": cached.color_map,
                "text_styles": cached.text_styles,
            }
        try:
            layout_root = self._read_xml(layout_part)
        except ET.ParseError as exc:
            self._warnings.append(
                ParseWarning(code="LAYOUT_XML_INVALID", message=f"Invalid slide layout XML: {exc}", locator=layout_part)
            )
            empty = _TemplateModel(layout_part, dict(self._theme), {}, dict(DEFAULT_COLOR_MAP), {})
            self._layout_cache[layout_part] = empty
            return {"theme": empty.theme, "placeholders": {}, "color_map": empty.color_map, "text_styles": {}}

        master_part = self._target_for(layout_part, SLIDE_MASTER_REL_TYPE)
        master_model: _TemplateModel | None = None
        if master_part is not None and self._pkg.exists(master_part):
            master_model = self._master_model(master_part)
        else:
            self._warnings.append(
                ParseWarning(
                    code="MASTER_PART_MISSING",
                    message=f"Slide master part missing: {master_part}",
                    locator=layout_part,
                )
            )
        master_model = master_model or _TemplateModel("", dict(self._theme), {}, {}, {})
        master_by_type = {
            key.removeprefix("type:"): (info["x"], info["y"], info["w"], info["h"])
            for key, info in master_model.placeholders.items()
            if key.startswith("type:") and all(info.get(name) is not None for name in ("x", "y", "w", "h"))
        }

        placeholders: dict[str, PlaceholderInfo] = {}
        for shape in _layout_shapes(layout_root):
            ph = _find_descendant(shape, "ph")
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

        color_map = {**DEFAULT_COLOR_MAP, **master_model.color_map, **self._clr_map_from(layout_root, override=False)}
        layout_styles = self._text_styles.parse(layout_root, color_map, theme=master_model.theme)
        model = _TemplateModel(
            layout_part,
            master_model.theme,
            placeholders,
            color_map,
            _merge_text_styles(master_model.text_styles, layout_styles),
        )
        self._layout_cache[layout_part] = model
        return {
            "theme": model.theme,
            "placeholders": model.placeholders,
            "color_map": model.color_map,
            "text_styles": model.text_styles,
        }

    def _master_model(self, master_part: str) -> _TemplateModel:
        cached = self._master_cache.get(master_part)
        if cached is not None:
            return cached
        try:
            master_root = self._read_xml(master_part)
        except ET.ParseError as exc:
            self._warnings.append(
                ParseWarning(code="MASTER_XML_INVALID", message=f"Invalid slide master XML: {exc}", locator=master_part)
            )
            model = _TemplateModel(master_part, dict(self._theme), {}, dict(DEFAULT_COLOR_MAP), {})
            self._master_cache[master_part] = model
            return model
        theme = self._theme_parser.parse_for_source(master_part) if self._theme_parser is not None else dict(self._theme)
        master_map = self._clr_map_from(master_root, override=False)
        color_map = {**DEFAULT_COLOR_MAP, **master_map}
        placeholders: dict[str, PlaceholderInfo] = {}
        for shape in _layout_shapes(master_root):
            ph = _find_descendant(shape, "ph")
            if ph is None:
                continue
            ph_type = ph.get("type", "obj")
            geometry = shape_geometry(shape, self._warnings)
            info: PlaceholderInfo = {"type": ph_type} if ph_type else {}
            if geometry is not None:
                info["x"], info["y"], info["w"], info["h"] = geometry
            if ph_type:
                placeholders[f"type:{ph_type}"] = info
        model = _TemplateModel(
            master_part,
            theme,
            placeholders,
            color_map,
            self._text_styles.parse(master_root, color_map, theme=theme),
        )
        self._master_cache[master_part] = model
        return model

    def _master_geometries(self, master_root: ET.Element) -> dict[str, tuple[int, int, int, int]]:
        geometries: dict[str, tuple[int, int, int, int]] = {}
        for shape in _layout_shapes(master_root):
            ph = _find_descendant(shape, "ph")
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
        cache_key = (source_part, rel_type)
        if cache_key in self._target_cache:
            return self._target_cache[cache_key]
        for record in self._relationships.by_source(source_part):
            if record.type == rel_type:
                self._target_cache[cache_key] = record.resolved_target
                return record.resolved_target
        self._target_cache[cache_key] = None
        return None

    def _read_xml(self, part: str) -> ET.Element:
        return self._pkg.read_xml(part)
