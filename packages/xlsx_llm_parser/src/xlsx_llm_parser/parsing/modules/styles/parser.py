"""Read the SpreadsheetML style table into a :class:`FormatIndex`."""

from __future__ import annotations

from typing import Literal
from xml.etree import ElementTree as ET

from ooxml_llm_core.package import PackageReader

from .index import FormatIndex
from .number_format import builtin_format_code
from .records import NS_S, differential_style, fill_info, font_info, parse_theme

StyleDetail = Literal["display", "structural", "semantic"]


def parse_styles(
    pkg: PackageReader,
    *,
    detail: StyleDetail = "semantic",
    include_semantic_details: bool | None = None,
    locale: str = "zh-CN",
) -> FormatIndex:
    """Parse the style layer needed by the selected output density.

    Numeric formats and protection are retained at every density.  Theme,
    font, fill, and differential-style trees are read only for semantic output.
    ``include_semantic_details`` remains as a compatibility spelling for older
    callers.
    """
    if include_semantic_details is not None:
        detail = "semantic" if include_semantic_details else "structural"
    index = FormatIndex(locale=locale)

    if not pkg.exists("xl/styles.xml"):
        return index

    include_semantic = detail == "semantic"
    theme = parse_theme(pkg) if include_semantic else {}
    root = pkg.read_xml("xl/styles.xml")
    custom_fmts = _parse_custom_formats(root)

    if include_semantic:
        _register_semantic_records(index, root, theme)

    style_xfs = _find_xfs(root, "cellStyleXfs")
    for xf in _find_xfs(root, "cellXfs"):
        num_fmt_id, format_code = _effective_number_format(xf, style_xfs, custom_fmts, locale)
        index.register_cell_format(
            num_fmt_id,
            format_code,
            font_id=_int_attr(xf, "fontId"),
            fill_id=_int_attr(xf, "fillId"),
            locked=_protection_flag(xf, "locked", default=True),
            formula_hidden=_protection_flag(xf, "hidden", default=False),
        )
    return index


def _parse_custom_formats(root: ET.Element) -> dict[int, str]:
    num_fmts = root.find(f"{{{NS_S}}}numFmts")
    if num_fmts is None:
        return {}
    return {_int_attr(num_fmt, "numFmtId"): num_fmt.get("formatCode", "") for num_fmt in num_fmts.findall(f"{{{NS_S}}}numFmt")}


def _register_semantic_records(
    index: FormatIndex,
    root: ET.Element,
    theme: dict[int, str],
) -> None:
    fonts = root.find(f"{{{NS_S}}}fonts")
    if fonts is not None:
        for font in fonts.findall(f"{{{NS_S}}}font"):
            index.register_font(font_info(font, theme))

    fills = root.find(f"{{{NS_S}}}fills")
    if fills is not None:
        for fill in fills.findall(f"{{{NS_S}}}fill"):
            index.register_fill(fill_info(fill, theme))

    dxfs = root.find(f"{{{NS_S}}}dxfs")
    if dxfs is not None:
        for dxf in dxfs.findall(f"{{{NS_S}}}dxf"):
            index.register_differential_style(differential_style(dxf, theme))


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


def _protection_flag(element: ET.Element, name: str, *, default: bool) -> bool:
    protection = element.find(f"{{{NS_S}}}protection")
    if protection is None:
        return default
    value = protection.get(name)
    if value is None:
        return default
    return value not in {"0", "false", "False"}


__all__ = ["StyleDetail", "parse_styles"]
