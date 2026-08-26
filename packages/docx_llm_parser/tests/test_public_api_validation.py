"""Validation contracts for public API inputs."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _fixtures import write_rich_docx
from docx_llm_parser import Density, ResourceType, get_resource, load_docx, parse_docx
from docx_llm_parser.core.enums import RevisionMode
from docx_llm_parser.core.models import ParseOptions
from docx_llm_parser.plan import DocxFeature, DocxParsePlan


def _docx_path() -> Path:
    temp = Path(TemporaryDirectory().name)
    # Not actually created — just for type validation tests that fail early
    return temp / "test.docx"


class PublicApiValidationTests(unittest.TestCase):
    def test_string_enums_preserve_serialized_values(self) -> None:
        self.assertEqual(str(Density.SEMANTIC), "semantic")
        self.assertEqual(str(RevisionMode.FINAL), "final")
        self.assertEqual(str(ResourceType.TABLES), "tables")

    def test_parse_plan_distinguishes_render_session_and_resource_work(self) -> None:
        plain = DocxParsePlan.render(Density.PLAIN)
        self.assertFalse(plain.needs(DocxFeature.CHARACTER_FORMATTING))
        self.assertFalse(plain.needs(DocxFeature.HEADERS))
        self.assertTrue(plain.needs(DocxFeature.BODY))
        self.assertTrue(DocxParsePlan.session().needs(DocxFeature.HEADERS))
        self.assertFalse(DocxParsePlan.resource(ResourceType.IMAGE).needs(DocxFeature.BODY))

    def test_density_rejects_unknown_value(self) -> None:

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            write_rich_docx(path)
            with self.assertRaisesRegex(ValueError, "density"):
                parse_docx(path, density="typo")

    def test_parse_options_reject_invalid_revision_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "revision_mode"):
            ParseOptions(revision_mode="typo")  # type: ignore[arg-type]

    def test_parse_options_normalizes_revision_mode(self) -> None:
        options = ParseOptions(revision_mode="review")  # type: ignore[arg-type]
        self.assertIs(options.revision_mode, RevisionMode.REVIEW)

    def test_loaded_facade_exposes_report_and_reuses_parsed_document(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            write_rich_docx(path)
            loaded = load_docx(path)
            self.assertEqual(loaded.report.format, "docx")
            self.assertIn("schemaVersion", loaded.report.to_dict())
            self.assertEqual(loaded.render(), loaded.render())
            self.assertTrue(list(loaded.iter_render(density=Density.PLAIN)))
            self.assertTrue(loaded.render_window(page=1))
            self.assertIsNone(loaded.get_resource("image", "missing"))
            with self.assertRaisesRegex(ValueError, "singular"):
                loaded.get_resource("images", "missing")

    def test_parse_stream_returns_output_iterator_after_parse(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            write_rich_docx(path)
            result = parse_docx(path, stream=True, density=Density.PLAIN)
            self.assertTrue(list(result))

    def test_parse_options_reject_non_positive_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be greater than zero"):
            ParseOptions(max_zip_entries=0)

    def test_get_resource_rejects_plural_type(self) -> None:

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            write_rich_docx(path)
            with self.assertRaisesRegex(ValueError, "singular"):
                get_resource(path, "images", "img1")

    def test_get_resource_unknown_type(self) -> None:

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            write_rich_docx(path)
            with self.assertRaisesRegex(ValueError, "Unknown resource type"):
                get_resource(path, "unknown", "id1")


if __name__ == "__main__":
    unittest.main()
