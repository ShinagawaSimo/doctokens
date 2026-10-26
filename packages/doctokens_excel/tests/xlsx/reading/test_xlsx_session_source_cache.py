"""Disposable source-byte ownership after a successful native-file parse."""

from doctokens_excel import open_xlsx

from test_support.paths import REPO_ROOT

FIXTURES = REPO_ROOT / "test_support/fixtures"


def test_ready_session_releases_source_bytes_and_keeps_resource_reader_open() -> None:
    with open_xlsx(FIXTURES / "xlsx/xlsx-sparse.xlsx") as session:
        package = session._package
        assert package._part_cache_bytes == 0 and not package._part_cache
        source = package.read_part("xl/workbook.xml")
        assert package._part_cache_bytes > 0
        package.clear_part_cache()
        package.clear_part_cache()
        assert package._part_cache_bytes == 0
        assert package.read_part("xl/workbook.xml") == source
        session.render()
