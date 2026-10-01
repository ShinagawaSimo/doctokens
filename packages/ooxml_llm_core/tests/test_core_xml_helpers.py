"""Missing-element guards; ordinary XML traversal is covered by file goldens."""

import unittest

from ooxml_llm_core.xml import child_elements, first_child

NS_DOCX = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


class XmlHelperGuardTests(unittest.TestCase):
    def test_first_child_returns_none_on_none_element(self) -> None:
        self.assertIsNone(first_child(None, "w", "r", ns=NS_DOCX))

    def test_child_elements_returns_empty_on_none(self) -> None:
        self.assertEqual(child_elements(None, "w", "r", ns=NS_DOCX), [])
