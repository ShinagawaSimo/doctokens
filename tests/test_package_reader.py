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
