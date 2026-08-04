"""Characterization tests for OOXML XML helper functions."""

import unittest
from xml.etree import ElementTree as ET

from ooxml_llm_core.xml import (
    attr,
    child_elements,
    first_child,
    local_name,
    qualified_name,
)

# Full DOCX namespace map used to verify ns-parameterized helpers work
NS_DOCX = {
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "xml": "http://www.w3.org/XML/1998/namespace",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}
TAG_W_P = qualified_name("w", "p", NS_DOCX)


class XmlHelpersTests(unittest.TestCase):
    def test_attr_returns_value(self) -> None:
        el = ET.fromstring(f'<w:p w:val="test" xmlns:w="{NS_DOCX["w"]}"/>')
        self.assertEqual(attr(el, "w", "val", ns=NS_DOCX), "test")

    def test_attr_returns_default_when_missing(self) -> None:
        el = ET.fromstring(f'<w:p xmlns:w="{NS_DOCX["w"]}"/>')
        self.assertEqual(attr(el, "w", "val", "fallback", ns=NS_DOCX), "fallback")

    def test_attr_returns_none_when_missing_no_default(self) -> None:
        el = ET.fromstring(f'<w:p xmlns:w="{NS_DOCX["w"]}"/>')
        self.assertIsNone(attr(el, "w", "val", ns=NS_DOCX))

    def test_first_child_returns_direct_child(self) -> None:
        el = ET.fromstring(
            f'<w:p xmlns:w="{NS_DOCX["w"]}"><w:r><w:t>text</w:t></w:r></w:p>'
        )
        result = first_child(el, "w", "r", ns=NS_DOCX)
        self.assertIsNotNone(result)
        self.assertEqual(local_name(result.tag), "r")

    def test_first_child_returns_none_on_none_element(self) -> None:
        self.assertIsNone(first_child(None, "w", "r", ns=NS_DOCX))

    def test_first_child_returns_none_when_no_match(self) -> None:
        el = ET.fromstring(f'<w:p xmlns:w="{NS_DOCX["w"]}"><w:r/></w:p>')
        self.assertIsNone(first_child(el, "w", "t", ns=NS_DOCX))

    def test_first_child_does_not_match_grandchild(self) -> None:
        el = ET.fromstring(
            f'<w:p xmlns:w="{NS_DOCX["w"]}"><w:r><w:t>text</w:t></w:r></w:p>'
        )
        self.assertIsNone(first_child(el, "w", "t", ns=NS_DOCX))

    def test_first_child_matches_first_of_many(self) -> None:
        el = ET.fromstring(
            f'<w:p xmlns:w="{NS_DOCX["w"]}"><w:r w:val="1"/><w:r w:val="2"/></w:p>'
        )
        result = first_child(el, "w", "r", ns=NS_DOCX)
        self.assertEqual(attr(result, "w", "val", ns=NS_DOCX), "1")

    def test_child_elements_returns_direct_children(self) -> None:
        el = ET.fromstring(
            f'<w:p xmlns:w="{NS_DOCX["w"]}"><w:r w:val="1"/><w:r w:val="2"/></w:p>'
        )
        children = child_elements(el, "w", "r", ns=NS_DOCX)
        self.assertEqual(len(children), 2)
        self.assertEqual(attr(children[0], "w", "val", ns=NS_DOCX), "1")

    def test_child_elements_returns_empty_on_none(self) -> None:
        self.assertEqual(child_elements(None, "w", "r", ns=NS_DOCX), [])

    def test_child_elements_returns_empty_when_none_match(self) -> None:
        el = ET.fromstring(f'<w:p xmlns:w="{NS_DOCX["w"]}"><w:r/></w:p>')
        self.assertEqual(child_elements(el, "w", "t", ns=NS_DOCX), [])

    def test_local_name_strips_namespace(self) -> None:
        self.assertEqual(local_name(TAG_W_P), "p")

    def test_local_name_no_namespace(self) -> None:
        self.assertEqual(local_name("p"), "p")

    def test_qualified_name_roundtrip(self) -> None:
        tag = qualified_name("w", "body", NS_DOCX)
        self.assertEqual(local_name(tag), "body")


if __name__ == "__main__":
    unittest.main()
