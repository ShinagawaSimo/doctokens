"""Choose table conditional regions from selected table geometry and saved flags."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ..model import StyleRecord
from .formatting import normalize_hex_color
from .namespaces import attr, first_child
from .styles import StyleMap

_ORDER = [
    "band1Vert",
    "band2Vert",
    "band1Horz",
    "band2Horz",
    "firstRow",
    "lastRow",
    "firstCol",
    "lastCol",
    "nwCell",
    "neCell",
    "swCell",
    "seCell",
]
_FLAGS = {
    "firstRow": "firstRow",
    "lastRow": "lastRow",
    "firstColumn": "firstCol",
    "lastColumn": "lastCol",
    "oddVBand": "band1Vert",
    "evenVBand": "band2Vert",
    "oddHBand": "band1Horz",
    "evenHBand": "band2Horz",
    "firstRowFirstColumn": "nwCell",
    "firstRowLastColumn": "neCell",
    "lastRowFirstColumn": "swCell",
    "lastRowLastColumn": "seCell",
}
_BITS = {"firstRow": 0x20, "lastRow": 0x40, "firstColumn": 0x80, "lastColumn": 0x100, "noHBand": 0x200, "noVBand": 0x400}


def _bool(value: str) -> bool:
    return value.lower() not in {"0", "false", "off"}


def table_look(node: ET.Element | None) -> dict[str, bool]:
    try:
        mask = int(attr(node, "w", "val") or "0", 16)
    except ValueError:
        mask = 0
    flags = {name: bool(mask & bit) for name, bit in _BITS.items()}
    for name in _BITS:
        if (value := attr(node, "w", name)) is not None:
            flags[name] = _bool(value)
    return flags


class TableStyleResolver:
    def __init__(self, styles: StyleMap, properties: ET.Element | None, rows: int, columns: int, headers: int = 0) -> None:
        self.styles = styles
        self.properties = properties
        self.style_id = attr(first_child(properties, "w", "tblStyle"), "w", "val")
        self.base = styles.table(self.style_id, [])
        self.rows, self.columns, self.headers = rows, columns, headers
        look = first_child(properties, "w", "tblLook")
        self.flags = table_look(look)
        self.row_band = self._band(properties, "tblStyleRowBandSize", self.base.row_band_size)
        self.col_band = self._band(properties, "tblStyleColBandSize", self.base.column_band_size)
        shading = first_child(properties, "w", "shd")
        self.direct_background = None
        if shading is not None:
            self.direct_background = normalize_hex_color(attr(shading, "w", "fill")) or ""
            if attr(shading, "w", "val") == "nil":
                self.direct_background = ""

    @staticmethod
    def _band(properties: ET.Element | None, name: str, inherited: int | None) -> int:
        try:
            return max(1, int(attr(first_child(properties, "w", name), "w", "val") or inherited or 1))
        except ValueError:
            return inherited or 1

    def row_exception(self, properties: ET.Element | None) -> TableStyleResolver:
        if properties is None:
            return self
        combined = ET.Element("table-properties")
        overrides = {child.tag: child for child in properties}
        for child in self.properties if self.properties is not None else ():
            if child.tag not in overrides:
                combined.append(child)
        combined.extend(overrides.values())
        return TableStyleResolver(self.styles, combined, self.rows, self.columns, self.headers)

    def cell(self, row: int, column: int, span: int, *properties: ET.Element | None) -> StyleRecord:
        flags = self.flags
        first_row = (row < max(1, self.headers)) and flags["firstRow"]
        last_row = row == self.rows - 1 and flags["lastRow"]
        first_col = column == 0 and flags["firstColumn"]
        last_col = column + span == self.columns and flags["lastColumn"]
        active = {
            "firstRow": first_row,
            "lastRow": last_row,
            "firstCol": first_col,
            "lastCol": last_col,
            "nwCell": first_row and first_col,
            "neCell": first_row and last_col,
            "swCell": last_row and first_col,
            "seCell": last_row and last_col,
        }
        if not flags["noHBand"] and not (first_row or last_row):
            band = max(0, row - (max(1, self.headers) if flags["firstRow"] else 0)) // self.row_band
            active["band1Horz" if band % 2 == 0 else "band2Horz"] = True
        if not flags["noVBand"] and not (first_col or last_col):
            band = max(0, column - int(flags["firstColumn"])) // self.col_band
            active["band1Vert" if band % 2 == 0 else "band2Vert"] = True
        for source in properties:
            cnf = first_child(source, "w", "cnfStyle")
            encoded = attr(cnf, "w", "val")
            if encoded and len(encoded) == 12 and set(encoded) <= {"0", "1"}:
                active.update({region: encoded[index] == "1" for index, region in enumerate(_FLAGS.values())})
            for name, region in _FLAGS.items():
                if (value := attr(cnf, "w", name)) is not None:
                    active[region] = _bool(value)
        resolved = self.styles.table(self.style_id, [region for region in _ORDER if active.get(region)])
        if self.direct_background is not None:
            resolved.cell_background = self.direct_background
        return resolved
