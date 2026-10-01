"""PackageReader security and OPC relationship tests."""

from __future__ import annotations

import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from docx_llm_parser.core.models import ParseOptions
from docx_llm_parser.core.package import (
    DocxPackageError,
    PackageReader,
    resolve_relationship_target,
    source_part_from_rels_path,
)

FIXTURE = Path(__file__).resolve().parents[3] / "test_support/fixtures/docx/docx-paragraph.docx"


class PackageReaderTests(unittest.TestCase):
    def test_package_validation_rejects_missing_parts_and_unsafe_entries(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            not_zip = temp / "not.docx"
            not_zip.write_text("plain", encoding="utf-8")
            with self.assertRaisesRegex(DocxPackageError, "Not a zip"):
                PackageReader(not_zip, ParseOptions()).__enter__()

            missing_content_types = temp / "missing-content-types.docx"
            _write_zip(missing_content_types, {"word/document.xml": "<w:document/>"})
            with (
                PackageReader(missing_content_types, ParseOptions()) as package,
                self.assertRaisesRegex(DocxPackageError, "Content_Types"),
            ):
                package.validate()

            missing_document = temp / "missing-document.docx"
            _write_zip(missing_document, {"[Content_Types].xml": _content_types()})
            with (
                PackageReader(missing_document, ParseOptions()) as package,
                self.assertRaisesRegex(DocxPackageError, "word/document.xml"),
            ):
                package.validate()

            too_many = temp / "too-many.docx"
            _write_zip(too_many, {"[Content_Types].xml": "", "word/document.xml": ""})
            with (
                PackageReader(too_many, ParseOptions(max_zip_entries=1)) as package,
                self.assertRaisesRegex(DocxPackageError, "Too many"),
            ):
                package.read_entry_index()

            too_large = temp / "too-large.docx"
            _write_zip(too_large, {"[Content_Types].xml": "12345", "word/document.xml": ""})
            with (
                PackageReader(
                    too_large,
                    ParseOptions(max_entry_uncompressed_bytes=3),
                ) as package,
                self.assertRaisesRegex(DocxPackageError, "Entry too large"),
            ):
                package.read_entry_index()

            unsafe = temp / "unsafe.docx"
            _write_zip(unsafe, {"[Content_Types].xml": "", "../evil.xml": ""})
            with (
                PackageReader(unsafe, ParseOptions()) as package,
                self.assertRaisesRegex(DocxPackageError, "parent traversal"),
            ):
                package.read_entry_index()

    def test_unusual_relationship_paths(self) -> None:
        # Nonstandard producers can use absolute targets or malformed rels paths.
        self.assertIsNone(source_part_from_rels_path("bad/path.rels"))
        self.assertEqual(
            resolve_relationship_target("word/document.xml", "/custom/item.xml", None),
            "custom/item.xml",
        )

    # ── A1 characterization: newly covered PackageReader branches ──

    def test_total_uncompressed_size_limit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "big.docx"
            _write_zip(
                path,
                {"[Content_Types].xml": _content_types(), "word/document.xml": "x" * 200_000},
            )
            with (
                PackageReader(path, ParseOptions(max_total_uncompressed_bytes=100_000)) as package,
                self.assertRaisesRegex(DocxPackageError, "too large"),
            ):
                package.read_entry_index()

    def test_total_uncompressed_at_boundary_passes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "boundary.docx"
            _write_zip(path, {"[Content_Types].xml": _content_types(), "word/document.xml": "123"})
            with PackageReader(path, ParseOptions(max_total_uncompressed_bytes=500)) as package:
                package.read_entry_index()

    def test_compression_ratio_rejects_suspicious_entry(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bomb.docx"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("[Content_Types].xml", _content_types())
                zf.writestr("word/document.xml", "")
                # Zero bytes compress extremely well.
                # 500_000 zero bytes with DEFLATE compress to ~500 bytes,
                # giving ratio ~0.001 < _MIN_INFLATE_RATIO (0.01).
                zf.writestr("word/large.bin", b"\x00" * 500_000)
            with (
                PackageReader(path, ParseOptions()) as package,
                self.assertRaisesRegex(DocxPackageError, "Suspicious compression ratio"),
            ):
                package.read_entry_index()

    def test_compression_ratio_grace_entry_bypasses_check(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "grace.docx"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("[Content_Types].xml", _content_types())
                zf.writestr("word/document.xml", "")
                # Entry at exactly _GRACE_ENTRY_SIZE (100_000) should NOT trigger check
                # (only entries > _GRACE_ENTRY_SIZE are checked)
                zf.writestr(zipfile.ZipInfo("word/exact.txt"), "A" * 100_000)
            with PackageReader(path, ParseOptions()) as package:
                package.read_entry_index()

    def test_duplicate_entry_case_insensitive_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dup.docx"
            _write_zip(
                path,
                {
                    "[Content_Types].xml": _content_types(),
                    "word/document.xml": "",
                    "word/Duplicate.xml": "",
                },
            )
            # Add a second entry that differs only in case
            with zipfile.ZipFile(path, "a") as zf:
                zf.writestr("word/duplicate.xml", "")
            with (
                PackageReader(path, ParseOptions()) as package,
                self.assertRaisesRegex(DocxPackageError, "Duplicate zip entry"),
            ):
                package.read_entry_index()

    def test_empty_entry_name_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty_name.docx"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("[Content_Types].xml", _content_types())
                zf.writestr("word/document.xml", "")
                zf.writestr(zipfile.ZipInfo(""), "")
            with (
                PackageReader(path, ParseOptions()) as package,
                self.assertRaisesRegex(DocxPackageError, "empty name"),
            ):
                package.read_entry_index()

    def test_absolute_path_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "abs.docx"
            _write_zip(path, {"[Content_Types].xml": _content_types(), "/word/document.xml": ""})
            with (
                PackageReader(path, ParseOptions()) as package,
                self.assertRaisesRegex(DocxPackageError, "absolute"),
            ):
                package.read_entry_index()

    def test_drive_letter_path_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "drive.docx"
            _write_zip(path, {"[Content_Types].xml": _content_types(), "C:/word/document.xml": ""})
            with (
                PackageReader(path, ParseOptions()) as package,
                self.assertRaisesRegex(DocxPackageError, "drive"),
            ):
                package.read_entry_index()

    def test_bytes_source(self) -> None:
        with PackageReader(FIXTURE.read_bytes(), ParseOptions()) as package:
            package.validate()

    def test_bytes_source_rejects_invalid(self) -> None:
        with self.assertRaisesRegex(DocxPackageError, "Not a valid zip"):
            PackageReader(b"not a zip file", ParseOptions()).__enter__()

    def test_exists_returns_false_for_missing(self) -> None:
        with PackageReader(FIXTURE, ParseOptions()) as package:
            self.assertFalse(package.exists("nonexistent.xml"))

    def test_open_entry_on_missing_raises(self) -> None:
        with (
            PackageReader(FIXTURE, ParseOptions()) as package,
            self.assertRaisesRegex(DocxPackageError, "Missing zip entry"),
        ):
            package.open_entry("nonexistent.xml")

    def test_zip_file_before_enter_raises(self) -> None:
        reader = PackageReader.__new__(PackageReader)
        reader._zip = None
        with self.assertRaisesRegex(DocxPackageError, "not open"):
            _ = reader.zip_file


def _write_zip(path: Path, entries: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def _content_types() -> str:
    return """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
</Types>"""


if __name__ == "__main__":
    unittest.main()
