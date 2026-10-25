"""Disposable source-byte ownership after a successful native-file parse."""

from pathlib import Path

from doctokens_word import open_docx

FIXTURES = Path(__file__).resolve().parents[3] / "test_support/fixtures"


def test_ready_session_releases_source_bytes_and_keeps_resource_reader_open() -> None:
    with open_docx(FIXTURES / "docx/docx-paragraph.docx") as session:
        package = session._package
        assert package._part_cache_bytes == 0 and not package._part_cache
        source = package.read_part("word/document.xml")
        assert package._part_cache_bytes > 0
        package.clear_part_cache()
        package.clear_part_cache()
        assert package._part_cache_bytes == 0
        assert package.read_part("word/document.xml") == source
        session.render()
