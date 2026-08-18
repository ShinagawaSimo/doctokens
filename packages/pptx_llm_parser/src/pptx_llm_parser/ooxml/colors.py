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

# Scheme default mapping (ECMA-376 §20.1.6.1): tx/bg names map to the dk/lt
# slots; accents and links map to themselves.
DEFAULT_COLOR_MAP: dict[str, str] = {
    "tx1": "dk1",
    "tx2": "dk2",
    "bg1": "lt1",
    "bg2": "lt2",
    "accent1": "accent1",
    "accent2": "accent2",
    "accent3": "accent3",
    "accent4": "accent4",
    "accent5": "accent5",
    "accent6": "accent6",
    "hlink": "hlink",
    "folHlink": "folHlink",
}

# Preset named colors (ECMA-376 §20.1.10.47).
_PRESET_COLORS: dict[str, str] = {
    "aliceBlue": "#F0F8FF",
    "antiqueWhite": "#FAEBD7",
    "aqua": "#00FFFF",
    "aquamarine": "#7FFFD4",
    "azure": "#F0FFFF",
    "beige": "#F5F5DC",
    "bisque": "#FFE4C4",
    "black": "#000000",
    "blanchedAlmond": "#FFEBCD",
    "blue": "#0000FF",
    "blueViolet": "#8A2BE2",
    "brown": "#A52A2A",
    "burlyWood": "#DEB887",
    "cadetBlue": "#5F9EA0",
    "chartreuse": "#7FFF00",
    "chocolate": "#D2691E",
    "coral": "#FF7F50",
    "cornflowerBlue": "#6495ED",
    "cornsilk": "#FFF8DC",
    "crimson": "#DC143C",
    "cyan": "#00FFFF",
    "darkBlue": "#00008B",
    "darkCyan": "#008B8B",
    "darkGoldenrod": "#B8860B",
    "darkGray": "#A9A9A9",
    "darkGreen": "#006400",
    "darkGrey": "#A9A9A9",
    "darkKhaki": "#BDB76B",
    "darkMagenta": "#8B008B",
    "darkOliveGreen": "#556B2F",
    "darkOrange": "#FF8C00",
    "darkOrchid": "#9932CC",
    "darkRed": "#8B0000",
    "darkSalmon": "#E9967A",
    "darkSeaGreen": "#8FBC8F",
    "darkSlateBlue": "#483D8B",
    "darkSlateGray": "#2F4F4F",
    "darkSlateGrey": "#2F4F4F",
    "darkTurquoise": "#00CED1",
    "darkViolet": "#9400D3",
    "deepPink": "#FF1493",
    "deepSkyBlue": "#00BFFF",
    "dimGray": "#696969",
    "dimGrey": "#696969",
    "dodgerBlue": "#1E90FF",
    "fireBrick": "#B22222",
    "floralWhite": "#FFFAF0",
    "forestGreen": "#228B22",
    "fuchsia": "#FF00FF",
    "gainsboro": "#DCDCDC",
    "ghostWhite": "#F8F8FF",
    "gold": "#FFD700",
    "goldenrod": "#DAA520",
    "gray": "#808080",
    "green": "#008000",
    "greenYellow": "#ADFF2F",
    "grey": "#808080",
    "honeydew": "#F0FFF0",
    "hotPink": "#FF69B4",
    "indianRed": "#CD5C5C",
    "indigo": "#4B0082",
    "ivory": "#FFFFF0",
    "khaki": "#F0E68C",
    "lavender": "#E6E6FA",
    "lavenderBlush": "#FFF0F5",
    "lawnGreen": "#7CFC00",
    "lemonChiffon": "#FFFACD",
    "lightBlue": "#ADD8E6",
    "lightCoral": "#F08080",
    "lightCyan": "#E0FFFF",
    "lightGoldenrodYellow": "#FAFAD2",
    "lightGray": "#D3D3D3",
    "lightGreen": "#90EE90",
    "lightGrey": "#D3D3D3",
    "lightPink": "#FFB6C1",
    "lightSalmon": "#FFA07A",
    "lightSeaGreen": "#20B2AA",
    "lightSkyBlue": "#87CEFA",
    "lightSlateGray": "#778899",
    "lightSlateGrey": "#778899",
    "lightSteelBlue": "#B0C4DE",
    "lightYellow": "#FFFFE0",
    "lime": "#00FF00",
    "limeGreen": "#32CD32",
    "linen": "#FAF0E6",
    "magenta": "#FF00FF",
    "maroon": "#800000",
    "mediumAquamarine": "#66CDAA",
    "mediumBlue": "#0000CD",
    "mediumOrchid": "#BA55D3",
    "mediumPurple": "#9370DB",
    "mediumSeaGreen": "#3CB371",
    "mediumSlateBlue": "#7B68EE",
    "mediumSpringGreen": "#00FA9A",
    "mediumTurquoise": "#48D1CC",
    "mediumVioletRed": "#C71585",
    "midnightBlue": "#191970",
    "mintCream": "#F5FFFA",
    "mistyRose": "#FFE4E1",
    "moccasin": "#FFE4B5",
    "navajoWhite": "#FFDEAD",
    "navy": "#000080",
    "oldLace": "#FDF5E6",
    "olive": "#808000",
    "oliveDrab": "#6B8E23",
    "orange": "#FFA500",
    "orangeRed": "#FF4500",
    "orchid": "#DA70D6",
    "paleGoldenrod": "#EEE8AA",
    "paleGreen": "#98FB98",
    "paleTurquoise": "#AFEEEE",
    "paleVioletRed": "#DB7093",
    "papayaWhip": "#FFEFD5",
    "peachPuff": "#FFDAB9",
    "peru": "#CD853F",
    "pink": "#FFC0CB",
    "plum": "#DDA0DD",
    "powderBlue": "#B0E0E6",
    "purple": "#800080",
    "red": "#FF0000",
    "rosyBrown": "#BC8F8F",
    "royalBlue": "#4169E1",
    "saddleBrown": "#8B4513",
    "salmon": "#FA8072",
    "sandyBrown": "#F4A460",
    "seaGreen": "#2E8B57",
    "seaShell": "#FFF5EE",
    "sienna": "#A0522D",
    "silver": "#C0C0C0",
    "skyBlue": "#87CEEB",
    "slateBlue": "#6A5ACD",
    "slateGray": "#708090",
    "slateGrey": "#708090",
    "snow": "#FFFAFA",
    "springGreen": "#00FF7F",
    "steelBlue": "#4682B4",
    "tan": "#D2B48C",
    "teal": "#008080",
    "thistle": "#D8BFD8",
    "tomato": "#FF6347",
    "turquoise": "#40E0D0",
    "violet": "#EE82EE",
    "wheat": "#F5DEB3",
    "white": "#FFFFFF",
    "whiteSmoke": "#F5F5F5",
    "yellow": "#FFFF00",
    "yellowGreen": "#9ACD32",
}

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
