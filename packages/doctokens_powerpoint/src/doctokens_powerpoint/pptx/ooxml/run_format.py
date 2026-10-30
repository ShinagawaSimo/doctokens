"""DrawingML character semantics shared by direct runs and inherited defaults."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from ..model.presentation import RunFormat
from .colors import is_default_text_color, resolve_color_element
from .namespaces import first_child


def drawingml_bool(value: str | None) -> bool:
    return value is not None and value.lower() not in {"0", "false", "off", "no"}


def character_format(
    properties: ET.Element,
    theme: dict[str, str],
    color_map: dict[str, str],
    warnings: list[ParseWarning],
    locator: str | None = None,
) -> RunFormat:
    """Retain explicit resets until all character-format layers have merged."""
    result: RunFormat = {}
    if (value := properties.get("b")) is not None:
        result["bold"] = drawingml_bool(value)
    if (value := properties.get("i")) is not None:
        result["italic"] = drawingml_bool(value)
    if (value := properties.get("u")) is not None:
        result["underline"] = value != "none"
    if (value := properties.get("strike")) is not None:
        result["strike"] = value in {"sngStrike", "dblStrike"}
    if (value := properties.get("baseline")) is not None:
        try:
            baseline = int(value)
        except ValueError:
            warnings.append(ParseWarning("TEXT_BASELINE_INVALID", f"Invalid text baseline: {value}", locator))
        else:
            result["superscript"] = baseline > 0
            result["subscript"] = baseline < 0
    for local, key in (("solidFill", "color"), ("highlight", "highlight")):
        container = first_child(properties, "a", local)
        if container is None:
            continue
        for child in container:
            color = resolve_color_element(child, theme, color_map=color_map, warnings=warnings, locator=locator)
            if color:
                # Empty color cancels an inherited non-default color. Highlight
                # is meaningful even when its resolved color is black.
                result[key] = "" if key == "color" and is_default_text_color(color) else color  # type: ignore[literal-required]
                break
    return result
