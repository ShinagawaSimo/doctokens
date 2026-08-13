"""Namespace map and precomputed tag constants."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from pptx_llm_parser.core import constants as const


class ConstantsTests(unittest.TestCase):
    def test_presentation_namespace_uris(self) -> None:
        self.assertEqual(
            const.NS["p"],
            "http://schemas.openxmlformats.org/presentationml/2006/main",
        )
        self.assertEqual(
            const.NS["a"],
            "http://schemas.openxmlformats.org/drawingml/2006/main",
        )
        self.assertEqual(
            const.NS["p14"],
            "http://schemas.microsoft.com/office/powerpoint/2010/main",
        )

    def test_qualified_name(self) -> None:
        self.assertEqual(
            const.qualified_name("p", "sld"),
            "{http://schemas.openxmlformats.org/presentationml/2006/main}sld",
        )

    def test_precomputed_tag_constants_match_qualified_names(self) -> None:
        for prefix, local in [
            ("p", "sld"),
            ("p", "cSld"),
            ("p", "spTree"),
            ("p", "sp"),
            ("p", "txBody"),
            ("p", "sldIdLst"),
            ("p", "sldId"),
            ("p", "sldSz"),
            ("a", "p"),
            ("a", "r"),
            ("a", "t"),
            ("a", "br"),
            ("a", "tab"),
        ]:
            tag = getattr(const, f"_TAG_{prefix.upper()}_{local.upper()}")
            self.assertEqual(tag, const.qualified_name(prefix, local))

    def test_local_name_strips_namespace(self) -> None:
        self.assertEqual(const.local_name(const._TAG_P_SP), "sp")
        self.assertEqual(const.local_name(const._TAG_A_BR), "br")

    def test_plain_attributes_are_unqualified(self) -> None:
        element = ET.fromstring(f'<p:sld xmlns:p="{const.NS["p"]}" show="0"/>')
        self.assertEqual(element.get("show"), "0")
        self.assertIsNone(element.get("absent"))

    def test_attr_reads_prefixed_attribute(self) -> None:
        element = ET.fromstring(f'<p:cNvPr xmlns:p="{const.NS["p"]}" xmlns:r="{const.NS["r"]}" id="2" r:id="rId1"/>')
        self.assertEqual(const.attr(element, "r", "id"), "rId1")
        self.assertIsNone(const.attr(element, "r", "absent"))

    def test_first_child_finds_namespaced_child(self) -> None:
        element = ET.fromstring(f'<p:sp xmlns:p="{const.NS["p"]}" xmlns:a="{const.NS["a"]}"><p:txBody><a:p/></p:txBody></p:sp>')
        body = const.first_child(element, "p", "txBody")
        self.assertIsNotNone(body)
        assert body is not None
        self.assertEqual(const.local_name(body.tag), "txBody")


if __name__ == "__main__":
    unittest.main()
