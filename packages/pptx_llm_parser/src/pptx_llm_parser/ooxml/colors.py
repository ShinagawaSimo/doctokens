"""DrawingML color element resolution.

Resolves any a:*-clr element against the deck theme: srgbClr, schemeClr
(with clrMap indirection + HSL luminance transforms), sysClr (lastClr
fallback), prstClr (ISO 29500 preset table), hslClr, scrgbClr, plus
tint/shade child transforms.
"""

from __future__ import annotations

import math
import re
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning

from ..core.constants import local_name
from .color_presets import _PRESET_COLORS
from .color_presets import DEFAULT_COLOR_MAP as DEFAULT_COLOR_MAP

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def is_default_text_color(value: str) -> bool:
    """Filter out colors close to default black to reduce output noise."""
    lowered = value.lower()
    if lowered in {"black", "#000000"}:
        return True
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return False
    red = int(value[1:3], 16)
    green = int(value[3:5], 16)
    blue = int(value[5:7], 16)
    return max(red, green, blue) <= 48 and max(red, green, blue) - min(red, green, blue) <= 16


def resolve_color_element(
    element: ET.Element,
    theme: dict[str, str],
    *,
    color_map: dict[str, str] | None = None,
    warnings: list[ParseWarning] | None = None,
    locator: str | None = None,
) -> str | None:
    """Resolve a DrawingML color element to #RRGGBB, or None when unknown."""
    mapping = color_map if color_map is not None else DEFAULT_COLOR_MAP
    name = local_name(element.tag)
    if name == "srgbClr":
        base = _normalize_hex(element.get("val"))
    elif name == "schemeClr":
        slot = mapping.get(element.get("val", ""))
        base = theme.get(slot) if slot else None
        if base is not None and not _HEX_RE.match(base):
            base = None
    elif name == "sysClr":
        base = _normalize_hex(element.get("lastClr"))
    elif name == "prstClr":
        base = _PRESET_COLORS.get(element.get("val", ""))
    elif name == "hslClr":
        base = _resolve_hsl_color(element, warnings=warnings, locator=locator)
    elif name == "scrgbClr":
        base = _resolve_scrgb_color(element, warnings=warnings, locator=locator)
    else:
        return None
    if base is None:
        return None
    return _apply_transforms(element, base, warnings=warnings, locator=locator)


def _apply_transforms(
    element: ET.Element,
    base: str,
    *,
    warnings: list[ParseWarning] | None,
    locator: str | None,
) -> str:
    """Apply tint/shade/lumMod child transforms in document order."""
    rgb = base
    for child in element:
        child_name = local_name(child.tag)
        value = child.get("val")
        parsed = _parse_number(value, child_name, warnings, locator)
        if child_name == "tint" and parsed is not None:
            rgb = _apply_linear_mix(rgb, parsed / 100000.0, toward_white=True)
        elif child_name == "shade" and parsed is not None:
            rgb = _apply_linear_mix(rgb, parsed / 100000.0, toward_white=False)
        elif child_name == "lumMod" and parsed is not None:
            lum_mod = parsed / 100000.0
            lum_off = _read_child_val(element, "lumOff", warnings, locator) / 100000.0
            rgb = _apply_luminance(rgb, lum_mod, lum_off)
        elif child_name == "alpha":
            # Alpha affects transparency, not the color value; ignored.
            continue
    return rgb


def _read_child_val(
    element: ET.Element,
    local: str,
    warnings: list[ParseWarning] | None,
    locator: str | None,
) -> float:
    for child in element:
        if local_name(child.tag) == local:
            value = child.get("val")
            if value is not None:
                return _parse_number(value, local, warnings, locator) or 0.0
    return 0.0


def _parse_number(
    value: str | None,
    field: str,
    warnings: list[ParseWarning] | None,
    locator: str | None,
) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("non-finite value")
        return parsed
    except (TypeError, ValueError):
        if warnings is not None:
            warnings.append(
                ParseWarning(
                    code="COLOR_VALUE_INVALID",
                    message=f"Invalid DrawingML color value for {field}: {value!r}",
                    locator=locator,
                )
            )
        return None


def _apply_luminance(rgb_hex: str, lum_mod: float, lum_off: float) -> str:
    r, g, b = _hex_to_rgb(rgb_hex)
    h, lum, s = _rgb_to_hsl(r, g, b)
    new_l = max(0.0, min(1.0, lum * lum_mod + lum_off))
    return _hsl_to_hex(h, new_l, s)


def _apply_linear_mix(rgb_hex: str, factor: float, *, toward_white: bool) -> str:
    r, g, b = _hex_to_rgb(rgb_hex)
    if toward_white:
        channels = (round(c * (1 - factor) + 255 * factor) for c in (r, g, b))
    else:
        channels = (round(c * (1 - factor)) for c in (r, g, b))
    return "#" + "".join(f"{max(0, min(255, c)):02X}" for c in channels)


def _resolve_hsl_color(
    element: ET.Element,
    *,
    warnings: list[ParseWarning] | None,
    locator: str | None,
) -> str | None:
    hue = element.get("hue")
    sat = element.get("sat")
    lum = element.get("lum")
    if hue is None or sat is None or lum is None:
        return None
    parsed = tuple(_parse_number(value, field, warnings, locator) for value, field in ((hue, "hue"), (sat, "sat"), (lum, "lum")))
    if any(value is None for value in parsed):
        return None
    h = (parsed[0] / 60000.0) % 360.0  # type: ignore[operator]
    s = parsed[1] / 100000.0  # type: ignore[operator]
    light = parsed[2] / 100000.0  # type: ignore[operator]
    return _hsl_to_hex(h, light, s)


def _resolve_scrgb_color(
    element: ET.Element,
    *,
    warnings: list[ParseWarning] | None,
    locator: str | None,
) -> str | None:
    r = element.get("r")
    g = element.get("g")
    b = element.get("b")
    if r is None or g is None or b is None:
        return None
    parsed = tuple(_parse_number(value, field, warnings, locator) for value, field in ((r, "r"), (g, "g"), (b, "b")))
    if any(value is None for value in parsed):
        return None
    channels = tuple(round(value / 100000.0 * 255) for value in parsed if value is not None)
    return "#" + "".join(f"{max(0, min(255, c)):02X}" for c in channels)


def _normalize_hex(value: str | None) -> str | None:
    if not value:
        return None
    if re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        return "#" + value.upper()
    return None


def _hex_to_rgb(rgb_hex: str) -> tuple[int, int, int]:
    return int(rgb_hex[1:3], 16), int(rgb_hex[3:5], 16), int(rgb_hex[5:7], 16)


def _rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    max_c = max(rf, gf, bf)
    min_c = min(rf, gf, bf)
    light = (max_c + min_c) / 2
    delta = max_c - min_c
    if delta == 0:
        return 0.0, light, 0.0
    s = delta / (1 - abs(2 * light - 1))
    if max_c == rf:
        h = 60 * (((gf - bf) / delta) % 6)
    elif max_c == gf:
        h = 60 * ((bf - rf) / delta + 2)
    else:
        h = 60 * ((rf - gf) / delta + 4)
    return h % 360.0, light, s


def _hsl_to_hex(h: float, light: float, s: float) -> str:
    c = (1 - abs(2 * light - 1)) * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = light - c / 2
    if h < 60:
        rf, gf, bf = c, x, 0.0
    elif h < 120:
        rf, gf, bf = x, c, 0.0
    elif h < 180:
        rf, gf, bf = 0.0, c, x
    elif h < 240:
        rf, gf, bf = 0.0, x, c
    elif h < 300:
        rf, gf, bf = x, 0.0, c
    else:
        rf, gf, bf = c, 0.0, x
    channels = (round((rf + m) * 255), round((gf + m) * 255), round((bf + m) * 255))
    return "#" + "".join(f"{max(0, min(255, c)):02X}" for c in channels)
