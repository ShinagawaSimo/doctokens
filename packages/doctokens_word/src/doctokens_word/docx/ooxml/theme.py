"""Saved Word theme colors, color-scheme mapping and byte luminance transforms."""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from ..model import ParseWarning, append_warning
from .namespaces import attr, first_child
from .package import PackageReader

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DEFAULT_MAP = {"background1": "light1", "text1": "dark1", "background2": "light2", "text2": "dark2"}
_SLOTS = {"dark1": "dk1", "light1": "lt1", "dark2": "dk2", "light2": "lt2", "hyperlink": "hlink", "followedHyperlink": "folHlink"}


@dataclass(slots=True)
class WordTheme:
    colors: dict[str, str] = field(default_factory=dict)
    mapping: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_MAP))
    warnings: list[ParseWarning] = field(default_factory=list)

    @classmethod
    def from_package(cls, package: PackageReader, warnings: list[ParseWarning]) -> WordTheme:
        result = cls(warnings=warnings)
        relationships = package.read_relationships_for_part("word/document.xml")
        relation = next((r for r in relationships if r.type.endswith("/theme")), None)
        part = relation.resolved_target if relation is not None else "word/theme/theme1.xml"
        if part and package.exists(part):
            try:
                root = package.read_xml(part)
            except ET.ParseError as exc:
                append_warning(warnings, "THEME_XML_INVALID", f"Invalid Word theme XML: {exc}", part=part)
            else:
                scheme = root.find(_A + "themeElements/" + _A + "clrScheme")
                if scheme is not None:
                    for slot in scheme:
                        name = slot.tag.rsplit("}", 1)[-1]
                        for color in slot:
                            raw = color.get("val") if color.tag == _A + "srgbClr" else color.get("lastClr")
                            if raw and re.fullmatch("[0-9A-Fa-f]{6}", raw):
                                result.colors[name] = "#" + raw.upper()
                                break
        settings = next((r.resolved_target for r in relationships if r.type.endswith("/settings")), "word/settings.xml")
        if settings and package.exists(settings):
            try:
                root = package.read_xml(settings)
            except ET.ParseError:
                return result
            mapping = first_child(root, "w", "clrSchemeMapping")
            if mapping is not None:
                for key in (
                    "bg1",
                    "t1",
                    "bg2",
                    "t2",
                    "accent1",
                    "accent2",
                    "accent3",
                    "accent4",
                    "accent5",
                    "accent6",
                    "hyperlink",
                    "followedHyperlink",
                ):
                    if value := attr(mapping, "w", key):
                        name = {"bg1": "background1", "t1": "text1", "bg2": "background2", "t2": "text2"}.get(key, key)
                        result.mapping[name] = value
        return result

    def color(self, node: ET.Element | None, *, fill: bool = False, literal: str = "val") -> str | None:
        if node is None:
            return None
        reference = attr(node, "w", "themeFill" if fill else "themeColor")
        fallback = attr(node, "w", "fill" if fill else literal)
        if reference:
            slot = self.mapping.get(reference, reference)
            slot = _SLOTS.get(slot, slot)
            value = self.colors.get(slot)
            if value:
                shade = attr(node, "w", "themeFillShade" if fill else "themeShade")
                tint = attr(node, "w", "themeFillTint" if fill else "themeTint")
                modifier = tint if tint is not None else shade
                if modifier is not None:
                    try:
                        if not re.fullmatch("[0-9A-Fa-f]{2}", modifier):
                            raise ValueError
                        factor = int(modifier, 16) / 255
                        rgb = [int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
                        hue, light, saturation = colorsys.rgb_to_hls(*rgb)
                        light = light * factor + (1 - factor) if tint is not None else light * factor
                        value = "#" + "".join(f"{round(c * 255):02X}" for c in colorsys.hls_to_rgb(hue, light, saturation))
                    except ValueError:
                        append_warning(
                            self.warnings, "THEME_COLOR_MODIFIER_INVALID", f"Invalid theme color modifier: {modifier!r}"
                        )
                return value
            append_warning(self.warnings, "THEME_COLOR_UNRESOLVED", f"Saved theme color cannot be resolved: {reference}")
        if fallback and fallback != "auto":
            return "#" + fallback.upper() if re.fullmatch("[0-9A-Fa-f]{6}", fallback) else fallback
        return None
