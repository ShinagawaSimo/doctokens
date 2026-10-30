"""Spreadsheet-specific theme/indexed palette and luminance transformations."""

from __future__ import annotations

import colorsys
import math
import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.reader import PackageReader

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_S = f"{{{NS_S}}}"
_SLOTS = ("lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink")
_THEME = ("FFFFFF", "000000", "E7E6E6", "44546A", "4472C4", "ED7D31", "A5A5A5", "FFC000", "5B9BD5", "70AD47", "0563C1", "954F72")
_PALETTE = [
    "000000",
    "FFFFFF",
    "FF0000",
    "00FF00",
    "0000FF",
    "FFFF00",
    "FF00FF",
    "00FFFF",
    "000000",
    "FFFFFF",
    "FF0000",
    "00FF00",
    "0000FF",
    "FFFF00",
    "FF00FF",
    "00FFFF",
    "800000",
    "008000",
    "000080",
    "808000",
    "800080",
    "008080",
    "C0C0C0",
    "808080",
    "9999FF",
    "993366",
    "FFFFCC",
    "CCFFFF",
    "660066",
    "FF8080",
    "0066CC",
    "CCCCCC",
    "000080",
    "FF00FF",
    "FFFF00",
    "00FFFF",
    "800080",
    "800000",
    "008080",
    "0000FF",
    "00CCFF",
    "CCFFFF",
    "CCFFCC",
    "FFFF99",
    "99CCFF",
    "FF99CC",
    "CC99FF",
    "FFCC99",
    "3366FF",
    "33CCCC",
    "99CC00",
    "FFCC00",
    "FF9900",
    "FF6600",
    "666699",
    "969696",
    "003366",
    "339966",
    "003300",
    "333300",
    "993300",
    "993366",
    "333399",
    "333333",
]


def _rgb(value: str | None) -> str | None:
    if value and re.fullmatch(r"(?:[0-9a-fA-F]{2})?[0-9a-fA-F]{6}", value):
        return value[-6:].upper()
    return None


@dataclass(slots=True)
class SpreadsheetColors:
    theme: dict[int, str] = field(default_factory=dict)
    indexed: list[str] = field(default_factory=lambda: list(_PALETTE))

    @classmethod
    def from_package(cls, package: PackageReader, styles: ET.Element | None) -> SpreadsheetColors:
        theme = dict(enumerate(_THEME))
        relationships = package.read_relationships_for_part("xl/workbook.xml")
        relationship = next((r for r in relationships if r.type.endswith("/theme")), None)
        part = relationship.resolved_target if relationship is not None else "xl/theme/theme1.xml"
        if part and package.exists(part):
            root = package.read_xml(part)
            scheme = root.find(_A + "themeElements/" + _A + "clrScheme")
            if scheme is not None:
                for index, slot in enumerate(_SLOTS):
                    source = scheme.find(_A + slot)
                    if source is not None:
                        for node in source:
                            value = _rgb(node.get("val") if node.tag == _A + "srgbClr" else node.get("lastClr"))
                            if value:
                                theme[index] = value
                                break
        result = cls(theme)
        if styles is not None:
            for index, node in enumerate(styles.findall(_S + "colors/" + _S + "indexedColors/" + _S + "rgbColor")):
                if index < 64 and (value := _rgb(node.get("rgb"))):
                    result.indexed[index] = value
        return result

    def resolve(self, node: ET.Element) -> str | None:
        if node.get("auto") in {"1", "true"}:
            return None
        base = _rgb(node.get("rgb"))
        try:
            if base is None and node.get("theme") is not None:
                base = self.theme.get(int(node.get("theme", "")))
            if base is None and node.get("indexed") is not None:
                index = int(node.get("indexed", ""))
                if 0 <= index < len(self.indexed):
                    base = self.indexed[index]
        except ValueError:
            return None
        if base and node.get("tint") is not None:
            try:
                tint = float(node.get("tint", ""))
                if not math.isfinite(tint) or not -1 <= tint <= 1:
                    return base
                red, green, blue = (int(base[i : i + 2], 16) / 255 for i in (0, 2, 4))
                hue, luminance, saturation = colorsys.rgb_to_hls(red, green, blue)
                luminance = luminance * (1 + tint) if tint < 0 else luminance * (1 - tint) + tint
                channels = colorsys.hls_to_rgb(hue, luminance, saturation)
                return "".join(f"{round(channel * 255):02X}" for channel in channels)
            except ValueError:
                return base
        return base
