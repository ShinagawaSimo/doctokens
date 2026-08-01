"""Validation contracts for public parser and renderer inputs."""

from __future__ import annotations

import unittest

from docx_llm_parser import (
    Density,
    ParsedDocument,
    ParseOptions,
    ResourceType,
    RevisionMode,
    get_resource,
    list_resources,
    parse_many,
    render_document,
    render_window,
)


def _empty_document() -> ParsedDocument:
    return ParsedDocument(
        metadata={},
        package_info={},
        blocks=[],
        relationships=[],
        styles=[],
        warnings=[],
    )


class PublicApiValidationTests(unittest.TestCase):
    def test_string_enums_preserve_serialized_values(self) -> None:
        self.assertEqual(str(Density.SEMANTIC), "L2")
        self.assertEqual(str(RevisionMode.FINAL), "final")
        self.assertEqual(str(ResourceType.TABLES), "tables")

    def test_density_rejects_unknown_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "density"):
            render_document(_empty_document(), density="typo")

    def test_window_rejects_invalid_page_and_span(self) -> None:
        with self.assertRaisesRegex(ValueError, "page"):
            render_window(_empty_document(), page=0)
        with self.assertRaisesRegex(ValueError, "span"):
            render_window(_empty_document(), page=1, span=0)

    def test_parse_options_reject_invalid_revision_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "revision_mode"):
            ParseOptions(revision_mode="typo")

    def test_parse_options_normalizes_revision_mode(self) -> None:
        options = ParseOptions(revision_mode="review")
        self.assertIs(options.revision_mode, RevisionMode.REVIEW)

    def test_parse_options_reject_non_positive_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_zip_entries"):
            ParseOptions(max_zip_entries=0)

    def test_parse_many_validates_before_starting_workers(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_workers"):
            parse_many([], "out", max_workers=0)
        with self.assertRaisesRegex(ValueError, "revision_mode"):
            parse_many([], "out", revision_mode="typo")

    def test_resource_plural_and_singular_contracts(self) -> None:
        parsed = _empty_document()
        self.assertEqual(list_resources(parsed, "images"), ())
        self.assertIsNone(get_resource(parsed, "image", "img1"))
        with self.assertRaisesRegex(ValueError, "singular"):
            get_resource(parsed, "images", "img1")
        with self.assertRaisesRegex(ValueError, "plural"):
            list_resources(parsed, "image")
        with self.assertRaisesRegex(ValueError, "Unknown resource type"):
            list_resources(parsed, "unknown")


if __name__ == "__main__":
    unittest.main()
