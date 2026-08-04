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
    rels_path_for_part,
    resolve_relationship_target,
    source_part_from_rels_path,
)


class PackageReaderTests(unittest.TestCase):
    def test_valid_package_reads_content_types_entries_and_relationships(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "valid.docx"
            _write_zip(
                path,
                {
                    "[Content_Types].xml": _content_types(),
                    "_rels/.rels": _relationships(
                        [
                            (
                                "rOffice",
                                "officeDocument",
                                "word/document.xml",
                                None,
                            )
                        ]
                    ),
                    "word/document.xml": "<w:document/>",
                    "word/_rels/document.xml.rels": _relationships(
                        [
                            ("rImage", "image", "media/image.png", None),
                            ("rExternal", "hyperlink", "https://example.test", "External"),
                        ],
                        include_noise=True,
                    ),
                    "word/media/image.png": "png",
                },
            )

            with PackageReader(path, ParseOptions()) as package:
                package.validate()
                self.assertTrue(package.exists("word/document.xml"))
                self.assertIs(package.read_entry_index(), package.read_entry_index())
                self.assertEqual(
                    package.read_content_types()["defaults"]["xml"],
                    "application/xml",
                )
                relationships = package.read_all_relationships()
                self.assertEqual(len(relationships), 3)
                self.assertEqual(relationships[1].resolved_target, "word/media/image.png")
                self.assertEqual(relationships[2].resolved_target, "https://example.test")
                self.assertEqual(package.open_entry("word\\document.xml").read(), b"<w:document/>")

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

    def test_relationship_path_helpers_cover_target_shapes(self) -> None:
        self.assertEqual(rels_path_for_part(None), "_rels/.rels")
        self.assertEqual(
            rels_path_for_part("word/document.xml"),
            "word/_rels/document.xml.rels",
        )
        self.assertEqual(source_part_from_rels_path("_rels/.rels"), None)
        self.assertEqual(
            source_part_from_rels_path("word/_rels/document.xml.rels"),
            "word/document.xml",
        )
        self.assertEqual(source_part_from_rels_path("bad/path.rels"), None)
        self.assertEqual(
            resolve_relationship_target("word/document.xml", "media/image.png", None),
            "word/media/image.png",
        )
        self.assertEqual(
            resolve_relationship_target("word/document.xml", "/custom/item.xml", None),
            "custom/item.xml",
        )
        self.assertEqual(
            resolve_relationship_target("word/document.xml", "https://example.test", "External"),
            "https://example.test",
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
                PackageReader(
                    path, ParseOptions(max_total_uncompressed_bytes=100_000)
                ) as package,
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

    def test_unencrypted_entries_pass_flag_check(self) -> None:
        """Verify that normal unencrypted entries are not flagged by the & 0x1 check."""
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "normal.docx"
            _write_zip(
                path,
                {"[Content_Types].xml": _content_types(), "word/document.xml": ""},
            )
            with PackageReader(path, ParseOptions()) as package:
                index = package.read_entry_index()
                for item in index:
                    self.assertFalse(
                        item["name"].startswith("word/secret"),
                        "normal entries should not be encrypted",
                    )
                self.assertEqual(len(index), 2)

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
            _write_zip(
                path, {"[Content_Types].xml": _content_types(), "C:/word/document.xml": ""}
            )
            with (
                PackageReader(path, ParseOptions()) as package,
                self.assertRaisesRegex(DocxPackageError, "drive"),
            ):
                package.read_entry_index()

    def test_content_types_override(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "override.docx"
            _write_zip(
                path,
                {
                    "[Content_Types].xml": (
                        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                        '<Default Extension="xml" ContentType="application/xml"/>'
                        '<Override PartName="/word/document.xml" '
                        'ContentType="application/custom+xml"/>'
                        "</Types>"
                    ),
                    "word/document.xml": "",
                },
            )
            with PackageReader(path, ParseOptions()) as package:
                ct = package.read_content_types()
                self.assertEqual(ct["defaults"]["xml"], "application/xml")
                self.assertEqual(ct["overrides"]["word/document.xml"], "application/custom+xml")

    def test_bytes_source(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tmp.docx"
            _write_zip(
                path,
                {"[Content_Types].xml": _content_types(), "word/document.xml": "<w:document/>"},
            )
            data = path.read_bytes()
            with PackageReader(data, ParseOptions()) as package:
                package.validate()
                self.assertTrue(package.exists("word/document.xml"))

    def test_bytes_source_rejects_invalid(self) -> None:
        with self.assertRaisesRegex(DocxPackageError, "Not a valid zip"):
            PackageReader(b"not a zip file", ParseOptions()).__enter__()

    def test_exists_returns_false_for_missing(self) -> None:
        path = Path(TemporaryDirectory().name) / "unused.docx"  # not actually used
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "exists_test.docx"
            _write_zip(
                path, {"[Content_Types].xml": _content_types(), "word/document.xml": ""}
            )
            with PackageReader(path, ParseOptions()) as package:
                self.assertFalse(package.exists("nonexistent.xml"))

    def test_open_entry_on_missing_raises(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "open_test.docx"
            _write_zip(
                path, {"[Content_Types].xml": _content_types(), "word/document.xml": ""}
            )
            with (
                PackageReader(path, ParseOptions()) as package,
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


def _relationships(
    rows: list[tuple[str, str, str, str | None]],
    *,
    include_noise: bool = False,
) -> str:
    noise = "<Ignored/>" if include_noise else ""
    body = "".join(_relationship(*row) for row in rows)
    return (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{noise}{body}</Relationships>"
    )


def _relationship(
    rel_id: str,
    rel_type: str,
    target: str,
    target_mode: str | None,
) -> str:
    mode = f' TargetMode="{target_mode}"' if target_mode else ""
    return (
        f'<Relationship Id="{rel_id}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{rel_type}" '
        f'Target="{target}"{mode}/>'
    )


if __name__ == "__main__":
    unittest.main()
