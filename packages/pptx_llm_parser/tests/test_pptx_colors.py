"""Theme light/dark and transparency cases await real PPTX files. Preset/scRGB/system encodings and exact transforms
cannot be requested reliably in the current Office UI; malformed colors remain exceptions.
"""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from pptx_llm_parser.ooxml.colors import resolve_color_element

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _color(xml: str) -> ET.Element:
    return ET.fromstring(f'<root xmlns:a="{A_NS}">{xml}</root>')[0]


def _theme(**slots: str) -> dict[str, str]:
    theme = {"dk1": "#000000", "lt1": "#FFFFFF", "accent1": "#4472C4"}
    theme.update(slots)
    return theme


class ColorResolutionTests(unittest.TestCase):
    def test_scheme_color_explicit_map(self) -> None:
        element = _color('<a:schemeClr val="accent1"/>')
        self.assertEqual(
            resolve_color_element(element, _theme(), color_map={"accent1": "lt1"}),
            "#FFFFFF",
        )

    def test_lum_mod_identity_and_extremes(self) -> None:
        base = _color('<a:schemeClr val="accent1"><a:lumMod val="100000"/></a:schemeClr>')
        self.assertEqual(resolve_color_element(base, _theme()), "#4472C4")
        off = _color('<a:schemeClr val="accent1"><a:lumMod val="0"/></a:schemeClr>')
        self.assertEqual(resolve_color_element(off, _theme()), "#000000")
        full = _color('<a:schemeClr val="accent1"><a:lumMod val="100000"/><a:lumOff val="100000"/></a:schemeClr>')
        self.assertEqual(resolve_color_element(full, _theme()), "#FFFFFF")

    def test_lum_mod_half_on_pure_red(self) -> None:
        red = _color('<a:srgbClr val="FF0000"><a:lumMod val="50000"/></a:srgbClr>')
        self.assertEqual(resolve_color_element(red, _theme()), "#800000")

    def test_lum_off_shifts_luminance(self) -> None:
        # L' = L*lumMod + lumOff: 0.5*1.0 + 0.5 = 1.0 → white; 0.5 + 0.25 = 0.75 → #FF8080.
        full = _color('<a:srgbClr val="FF0000"><a:lumMod val="100000"/><a:lumOff val="50000"/></a:srgbClr>')
        self.assertEqual(resolve_color_element(full, _theme()), "#FFFFFF")
        partial = _color('<a:srgbClr val="FF0000"><a:lumMod val="100000"/><a:lumOff val="25000"/></a:srgbClr>')
        self.assertEqual(resolve_color_element(partial, _theme()), "#FF8080")

    def test_sys_color_uses_last_clr(self) -> None:
        self.assertEqual(
            resolve_color_element(_color('<a:sysClr val="windowText" lastClr="44546A"/>'), _theme()),
            "#44546A",
        )

    def test_preset_color(self) -> None:
        self.assertEqual(resolve_color_element(_color('<a:prstClr val="aliceBlue"/>'), _theme()), "#F0F8FF")

    def test_unknown_preset_color_returns_none(self) -> None:
        self.assertIsNone(resolve_color_element(_color('<a:prstClr val="notAColor"/>'), _theme()))

    def test_hsl_color(self) -> None:
        element = _color('<a:hslClr hue="0" sat="100000" lum="50000"/>')
        self.assertEqual(resolve_color_element(element, _theme()), "#FF0000")

    def test_scrgb_color(self) -> None:
        element = _color('<a:scrgbClr r="100000" g="0" b="0"/>')
        self.assertEqual(resolve_color_element(element, _theme()), "#FF0000")

    def test_tint_lightens(self) -> None:
        element = _color('<a:srgbClr val="FF0000"><a:tint val="50000"/></a:srgbClr>')
        self.assertEqual(resolve_color_element(element, _theme()), "#FF8080")

    def test_shade_darkens(self) -> None:
        element = _color('<a:srgbClr val="FF0000"><a:shade val="50000"/></a:srgbClr>')
        self.assertEqual(resolve_color_element(element, _theme()), "#800000")

    def test_alpha_is_ignored(self) -> None:
        element = _color('<a:srgbClr val="FF0000"><a:alpha val="50000"/></a:srgbClr>')
        self.assertEqual(resolve_color_element(element, _theme()), "#FF0000")


if __name__ == "__main__":
    unittest.main()
