"""Unit coverage for the shared DTP/DTX output primitives."""

import unittest
from xml.etree import ElementTree as ET

from ooxml_llm_core.doctokens_plain import page_marker, render_plain, validate_plain
from ooxml_llm_core.doctokens_xml import append, element, serialize, text, validate_xml


class DoctokensPlainTests(unittest.TestCase):
    def test_header_and_internal_page_marker_are_rendered(self) -> None:
        output = render_plain(
            f"density=plain\n{page_marker(1)}\nFirst\n{page_marker(2)}\nSecond",
            format_name="docx",
            pagination="last-rendered-hints",
            revision_view="final",
        )
        validate_plain(output, format_name="docx")
        self.assertIn("<page=1>\nFirst\n<page=2>\nSecond", output)

    def test_user_text_that_matches_page_marker_is_escaped(self) -> None:
        output = render_plain("density=plain\n<page=2>\nsource text", format_name="docx")
        validate_plain(output, format_name="docx")
        self.assertIn("\\<page=2>\nsource text", output)

    def test_user_page_escape_is_escaped_again(self) -> None:
        output = render_plain("density=plain\n\\<page=2>", format_name="docx")
        self.assertIn("\\\\<page=2>", output)


class DoctokensXmlTests(unittest.TestCase):
    def test_direct_element_tree_is_well_formed_and_escapes_text(self) -> None:
        root = element("document", density="structural", format="docx", schema="doctokens-xml", version="1.0")
        paragraph = append(root, "p")
        text(paragraph, "A < B")
        output = serialize(root)
        validate_xml(output)
        self.assertEqual(ET.fromstring(output).findtext("p"), "A < B")

    def test_validator_rejects_wrong_root_and_format(self) -> None:
        with self.assertRaises(ValueError):
            validate_xml('<wrong schema="doctokens-xml" version="1.0" format="docx"/>')
        with self.assertRaises(ValueError):
            validate_xml('<document schema="doctokens-xml" version="1.0" format="xlsx"/>')


if __name__ == "__main__":
    unittest.main()
