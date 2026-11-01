"""Read the SpreadsheetML style table into a :class:`FormatIndex`."""

from __future__ import annotations

from typing import Literal
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.reader import PackageReader

from doctokens_excel.formatting.values import builtin_format_code

from .colors import SpreadsheetColors
from .index import FormatIndex
from .records import NS_S, differential_style, fill_info, font_info

StyleDetail = Literal["display", "structural", "semantic"]


def parse_styles(
    pkg: PackageReader,
    *,
    detail: StyleDetail = "semantic",
    locale: str = "zh-CN",
) -> FormatIndex:
    """Parse the style layer needed by the selected output density.

    Numeric formats and protection are retained at every density. Theme and
    differential styles also resolve structural color-filter conditions;
    ordinary font/fill records are needed only for semantic output.
    """
    index = FormatIndex(locale=locale)

    root = pkg.read_xml("xl/styles.xml") if pkg.exists("xl/styles.xml") else None
    include_semantic = detail == "semantic"
    index.colors = SpreadsheetColors.from_package(pkg, root) if detail != "display" else SpreadsheetColors()
    if root is None:
        return index
    custom_fmts = _parse_custom_formats(root)

    if include_semantic:
        _register_semantic_records(index, root, index.colors)
    if detail != "display":
        for dxf in root.findall(f"{{{NS_S}}}dxfs/{{{NS_S}}}dxf"):
            index.register_differential_style(differential_style(dxf, index.colors))

    style_xfs = _find_xfs(root, "cellStyleXfs")
    visible_fills = _visible_records(root, "fills", "fill")
    visible_borders = _visible_records(root, "borders", "border")
    for xf in _find_xfs(root, "cellXfs"):
        num_fmt_id, format_code = _effective_number_format(xf, style_xfs, custom_fmts, locale)
        index.register_cell_format(
            num_fmt_id,
            format_code,
            font_id=_effective_style_id(xf, style_xfs, "font"),
            fill_id=_effective_style_id(xf, style_xfs, "fill"),
            locked=_protection_flag(xf, style_xfs, "locked", default=True),
            formula_hidden=_protection_flag(xf, style_xfs, "hidden", default=False),
            visible_blank=(
                _effective_style_id(xf, style_xfs, "fill") in visible_fills
                or _effective_style_id(xf, style_xfs, "border") in visible_borders
            ),
        )
    return index


def _effective_style_id(xf: ET.Element, parents: list[ET.Element], kind: str) -> int:
    parent_index = _int_attr(xf, "xfId", -1)
    parent = parents[parent_index] if 0 <= parent_index < len(parents) else None
    if parent is not None and ((xf.get(f"apply{kind.title()}") or "1").lower() in {"0", "false"} or xf.get(f"{kind}Id") is None):
        return _int_attr(parent, f"{kind}Id")
    return _int_attr(xf, f"{kind}Id")


def _visible_records(root: ET.Element, group: str, kind: str) -> set[int]:
    """Read only presence of visible blank formatting, without theme resolution."""
    visible: set[int] = set()
    for index, record in enumerate(root.findall(f"{{{NS_S}}}{group}/{{{NS_S}}}{kind}")):
        for child in record:
            if kind == "fill":
                if child.tag == f"{{{NS_S}}}gradientFill" or child.get("patternType", "none") != "none":
                    visible.add(index)
            elif child.get("style") not in {None, "none"}:
                visible.add(index)
    return visible


def _parse_custom_formats(root: ET.Element) -> dict[int, str]:
    num_fmts = root.find(f"{{{NS_S}}}numFmts")
    if num_fmts is None:
        return {}
    return {_int_attr(num_fmt, "numFmtId"): num_fmt.get("formatCode", "") for num_fmt in num_fmts.findall(f"{{{NS_S}}}numFmt")}


def _register_semantic_records(
    index: FormatIndex,
    root: ET.Element,
    colors: SpreadsheetColors,
) -> None:
    fonts = root.find(f"{{{NS_S}}}fonts")
    if fonts is not None:
        for font in fonts.findall(f"{{{NS_S}}}font"):
            index.register_font(font_info(font, colors))

    fills = root.find(f"{{{NS_S}}}fills")
    if fills is not None:
        for fill in fills.findall(f"{{{NS_S}}}fill"):
            index.register_fill(fill_info(fill, colors))


def _find_xfs(root: ET.Element, name: str) -> list[ET.Element]:
    parent = root.find(f"{{{NS_S}}}{name}")
    return [] if parent is None else parent.findall(f"{{{NS_S}}}xf")


def _effective_number_format(
    xf: ET.Element,
    style_xfs: list[ET.Element],
    custom_fmts: dict[int, str],
    locale: str,
) -> tuple[int, str]:
    """Resolve a cell XF's number format, including its style-XF parent."""
    direct_id = _int_attr(xf, "numFmtId")
    has_direct_id = xf.get("numFmtId") is not None
    parent_index = _int_attr(xf, "xfId", default=-1)
    parent = style_xfs[parent_index] if 0 <= parent_index < len(style_xfs) else None

    if parent is None:
        resolved_id = direct_id
    elif xf.get("applyNumberFormat", "1").lower() in {"0", "false"}:
        resolved_id = _int_attr(parent, "numFmtId")
    elif has_direct_id:
        resolved_id = direct_id
    else:
        # A cell XF may omit numFmtId and inherit the style XF.  Treating the
        # missing attribute as an implicit zero loses custom parent formats.
        resolved_id = _int_attr(parent, "numFmtId")

    return resolved_id, custom_fmts.get(resolved_id, builtin_format_code(resolved_id, locale))


def _int_attr(element: ET.Element, name: str, default: int = 0) -> int:
    try:
        return int(element.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _protection_flag(element: ET.Element, parents: list[ET.Element], name: str, *, default: bool) -> bool | None:
    protection = element.find(f"{{{NS_S}}}protection")
    apply = element.get("applyProtection")
    if apply not in {None, "0", "1", "true", "false"}:
        return None
    if protection is None or apply in {"0", "false"}:
        index = _int_attr(element, "xfId", -1)
        parent = parents[index] if 0 <= index < len(parents) else None
        protection = parent.find(f"{{{NS_S}}}protection") if parent is not None else None
    if protection is None:
        return default
    value = protection.get(name)
    if value is None:
        return default
    if value in {"1", "true"}:
        return True
    return False if value in {"0", "false"} else None


__all__ = ["StyleDetail", "parse_styles"]
