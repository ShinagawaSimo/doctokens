"""Tests for the shared PackageReader with PackageLimits."""

import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.options import PackageOptions
from ooxml_llm_core.package import (
    PackageError,
    PackageReader,
)
from ooxml_llm_core.xml import parse_xml


def _write_zip(path: Path, entries: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def _content_types() -> str:
    return """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
</Types>"""


FIXTURE = Path(__file__).resolve().parents[3] / "test_support/fixtures/docx/docx-paragraph.docx"


class CorePackageReaderTests(unittest.TestCase):
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

    def test_bytes_source(self) -> None:
        with PackageReader(FIXTURE.read_bytes(), PackageLimits()) as package:
            package.validate(required_part="word/document.xml")

    def test_bytes_source_rejects_invalid(self) -> None:
        with self.assertRaisesRegex(PackageError, "Not a valid zip"):
            PackageReader(b"not a zip file", PackageLimits()).__enter__()

    def test_small_parts_are_cached_but_xml_trees_are_not_shared(self) -> None:
        with PackageReader(FIXTURE, PackageLimits()) as package:
            self.assertIs(package.read_entry_index(), package.read_entry_index())
            first_bytes = package.read_part("word/document.xml")
            second_bytes = package.read_part("word\\document.xml")
            self.assertIs(first_bytes, second_bytes)
            first_root = package.read_xml("word/document.xml")
            original = ET.tostring(first_root)
            first_root.clear()
            second_root = package.read_xml("word/document.xml")
            self.assertEqual(ET.tostring(second_root), original)

    def test_large_part_does_not_enter_the_session_cache(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            large_part = "word/large.xml"
            _write_zip(
                path,
                {
                    "[Content_Types].xml": _content_types(),
                    large_part: "<root>" + "x" * (512 * 1024 + 1) + "</root>",
                },
            )
            with PackageReader(path, PackageLimits()) as package:
                root = package.read_xml(large_part)
                self.assertEqual(root.tag, "root")
                self.assertNotIn(large_part, package._part_cache)
                self.assertEqual(package._part_cache_bytes, 0)

    def test_xml_backend_preserves_parse_errors_and_disables_external_entities(self) -> None:
        with self.assertRaises(ET.ParseError):
            parse_xml(b"<root>")

        payload = b'<!DOCTYPE root [<!ENTITY secret SYSTEM "file:///not-readable">]><root>&secret;</root>'
        try:
            root = parse_xml(payload)
        except ET.ParseError:
            return
        self.assertNotIn("not-readable", "".join(root.itertext()))

    def test_relationship_records_are_cached_with_independent_lists(self) -> None:
        with PackageReader(FIXTURE, PackageLimits()) as package:
            first = package.read_relationships_for_part("word/document.xml")
            expected = first.copy()
            self.assertTrue(expected)
            first.clear()
            second = package.read_relationships_for_part("word/document.xml")
            self.assertEqual(second, expected)

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
