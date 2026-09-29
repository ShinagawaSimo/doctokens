"""Geometry."""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning

from ....core.constants import attr, first_child, local_name
from ....core.models import (
    AssetLookup,
    LayoutContext,
    ShapeBlock,
    SlideBackground,
)
from ....ooxml.colors import resolve_color_element
from ....ooxml.inheritance import shape_geometry
from .shape_details import _find_descendant


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


class SlideGeometry:
    """Apply group transforms, placeholder geometry, and explicit backgrounds."""

    def __init__(
        self,
        warnings: list[ParseWarning],
        assets: AssetLookup,
        slide_size: tuple[int, int] | None,
        *,
        include_geometry: bool,
        include_theme_layout: bool,
    ) -> None:
        self._warnings = warnings
        self._asset_lookup = assets
        self._slide_size = slide_size
        self.include_geometry = include_geometry
        self.include_theme_layout = include_theme_layout

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
        blip = _find_descendant(bg, "blip")
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
        ph = _find_descendant(element, "ph")
        idx = ph.get("idx", "0") if ph is not None else None
        own_type = ph.get("type") if ph is not None else None
        inherited = None
        if self.include_theme_layout:
            inherited = context["placeholders"].get(idx or "")
            if inherited is None and own_type:
                inherited = context["placeholders"].get(f"type:{own_type}")
        if ph is not None and ph.get("type"):
            shape["placeholderType"] = ph.get("type") or ""
        elif inherited is not None and inherited.get("type"):
            shape["placeholderType"] = inherited["type"]
        geometry = None
        if self.include_geometry:
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
