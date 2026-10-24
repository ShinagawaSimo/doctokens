"""Text styles."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from doctokens_core.models import ParseWarning

from ..core.constants import first_child, local_name
from ..core.models import ParagraphStyle, RunFormat
from .bullet_fonts import font_declaration, text_font
from .colors import is_default_text_color, resolve_color_element


def merge_paragraph_style(base: ParagraphStyle, overlay: ParagraphStyle) -> ParagraphStyle:
    merged = cast(ParagraphStyle, dict(base))
    if overlay.get("listNone") or "bullet" in overlay or "numberType" in overlay:
        untyped = cast(dict[str, object], merged)
        for key in ("bullet", "numberType", "startAt", "listNone"):
            untyped.pop(key, None)
    merged.update(overlay)
    if "runFormat" in overlay:
        merged["runFormat"] = {**base.get("runFormat", {}), **overlay["runFormat"]}
    return merged


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
            target[level] = merge_paragraph_style(target.get(level, {}), style)
    return result


def _layout_shapes(layout_root: ET.Element) -> list[ET.Element]:
    c_sld = first_child(layout_root, "p", "cSld")
    sp_tree = first_child(c_sld, "p", "spTree") if c_sld is not None else None
    if sp_tree is None:
        return []
    return [child for child in sp_tree if local_name(child.tag) == "sp"]


def _find_descendant(element: ET.Element, local: str) -> ET.Element | None:
    for descendant in element.iter():
        if local_name(descendant.tag) == local:
            return descendant
    return None


class TextStyleParser:
    """Read inherited paragraph/run defaults using one theme and warning sink."""

    def __init__(self, theme: dict[str, str], warnings: list[ParseWarning], *, include_formatting: bool = True) -> None:
        self._theme = theme
        self._warnings = warnings
        self._include_formatting = include_formatting

    def parse(
        self,
        root: ET.Element,
        color_map: dict[str, str],
        *,
        theme: dict[str, str] | None = None,
    ) -> dict[str, dict[int, ParagraphStyle]]:
        result: dict[str, dict[int, ParagraphStyle]] = {}
        tx_styles = _find_descendant(root, "txStyles")
        if tx_styles is not None:
            role_names = {"titleStyle": "title", "bodyStyle": "body", "otherStyle": "other"}
            for child in tx_styles:
                role = role_names.get(local_name(child.tag))
                if role:
                    result[role] = self.paragraph_defaults(child, color_map, theme=theme)
        for shape in _layout_shapes(root):
            ph = _find_descendant(shape, "ph")
            tx_body = first_child(shape, "p", "txBody")
            lst_style = first_child(tx_body, "a", "lstStyle") if tx_body is not None else None
            if ph is None or lst_style is None:
                continue
            styles = self.paragraph_defaults(lst_style, color_map, theme=theme)
            if not styles:
                continue
            result[f"idx:{ph.get('idx', '0')}"] = styles
            result[f"type:{ph.get('type', 'obj')}"] = styles
        return result

    def paragraph_defaults(
        self,
        container: ET.Element,
        color_map: dict[str, str],
        *,
        theme: dict[str, str] | None = None,
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
            font = first_child(child, "a", "buFont")
            if font is not None:
                style["bulletFont"], style["bulletFontSymbol"] = font_declaration(font)
            elif first_child(child, "a", "buFontTx") is not None:
                style["bulletFont"] = ""
                style["bulletFontSymbol"] = False
            bullet = first_child(child, "a", "buChar")
            auto = first_child(child, "a", "buAutoNum")
            if first_child(child, "a", "buNone") is not None:
                style["listNone"] = True
            elif bullet is not None and bullet.get("char"):
                style["bullet"] = bullet.get("char", "")
            elif auto is not None:
                style["numberType"] = auto.get("type", "arabicPeriod")
                try:
                    style["startAt"] = int(auto.get("startAt", "1"))
                except ValueError:
                    style["startAt"] = 1
            def_r_pr = first_child(child, "a", "defRPr")
            if declaration := text_font(def_r_pr):
                style["textFont"], style["textFontSymbol"] = declaration
            if self._include_formatting and def_r_pr is not None:
                run_format = self._run_defaults(def_r_pr, color_map, theme=theme)
                if run_format:
                    style["runFormat"] = run_format
            if style:
                result[level] = style
        return result

    def _run_defaults(
        self,
        r_pr: ET.Element,
        color_map: dict[str, str],
        *,
        theme: dict[str, str] | None = None,
    ) -> RunFormat:
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
                    theme or self._theme,
                    color_map=color_map,
                    warnings=self._warnings,
                )
                if color and not is_default_text_color(color):
                    result["color"] = color
                    break
        return result
