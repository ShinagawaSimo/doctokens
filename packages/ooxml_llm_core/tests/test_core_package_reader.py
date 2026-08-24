"""Tests for the shared PackageReader with PackageLimits."""

import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.options import PackageOptions
from ooxml_llm_core.package import (
    PackageError,
    PackageReader,
    rels_path_for_part,
    resolve_relationship_target,
    source_part_from_rels_path,
)


def _write_zip(path: Path, entries: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def _content_types() -> str:
    return """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
</Types>"""


class CorePackageReaderTests(unittest.TestCase):
    def test_happy_path_with_required_part(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            _write_zip(
                path,
                {"[Content_Types].xml": _content_types(), "word/document.xml": "<w:document/>"},
            )
            with PackageReader(path, PackageLimits()) as package:
                package.validate(required_part="word/document.xml")
                self.assertTrue(package.exists("word/document.xml"))
                self.assertEqual(len(package.read_all_relationships()), 0)

    def test_missing_required_part(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            _write_zip(path, {"[Content_Types].xml": _content_types()})
            with (
                PackageReader(path, PackageLimits()) as package,
                self.assertRaisesRegex(PackageError, "missing_part"),
            ):
                package.validate(required_part="missing_part")

    def test_excessive_entries(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            _write_zip(path, {"[Content_Types].xml": "", "word/document.xml": ""})
            with (
                PackageReader(path, PackageLimits(max_zip_entries=1)) as package,
                self.assertRaisesRegex(PackageError, "Too many"),
            ):
                package.read_entry_index()

    def test_path_helpers(self) -> None:
        self.assertEqual(rels_path_for_part(None), "_rels/.rels")
        self.assertEqual(
            rels_path_for_part("word/document.xml"),
            "word/_rels/document.xml.rels",
        )
        self.assertIsNone(source_part_from_rels_path("_rels/.rels"))
        self.assertEqual(
            source_part_from_rels_path("word/_rels/document.xml.rels"),
            "word/document.xml",
        )
        self.assertEqual(
            resolve_relationship_target("word/document.xml", "media/image.png", None),
            "word/media/image.png",
        )
        self.assertEqual(
            resolve_relationship_target("word/document.xml", "https://example.test", "External"),
            "https://example.test",
        )

    def test_bytes_source(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            _write_zip(
                path,
                {"[Content_Types].xml": _content_types(), "word/document.xml": "<w:document/>"},
            )
            data = path.read_bytes()
            with PackageReader(data, PackageLimits()) as package:
                package.validate(required_part="word/document.xml")
                self.assertTrue(package.exists("word/document.xml"))

    def test_bytes_source_rejects_invalid(self) -> None:
        with self.assertRaisesRegex(PackageError, "Not a valid zip"):
            PackageReader(b"not a zip file", PackageLimits()).__enter__()

    def test_limits_and_unsafe_entry_names_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_zip_entries"):
            PackageLimits(max_zip_entries=0)
        for name in ("/absolute.xml", "C:/drive.xml", "../parent.xml"):
            with self.subTest(name=name), self.assertRaisesRegex(PackageError, "Unsafe"):
                PackageReader._validate_entry_name(name)

    def test_common_ocr_option_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "ocr_workers"):
            PackageOptions.validate_ocr_options(None, 0, 1.0)
        with self.assertRaisesRegex(ValueError, "ocr_timeout"):
            PackageOptions.validate_ocr_options(None, 1, float("inf"))
        with self.assertRaisesRegex(TypeError, "ocr must provide"):
            PackageOptions.validate_ocr_options(object(), 1, 1.0)
