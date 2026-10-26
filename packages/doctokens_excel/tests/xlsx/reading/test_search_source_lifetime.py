import pytest
from doctokens_excel import XlsxTextSource

from test_support.paths import REPO_ROOT

FIXTURES = REPO_ROOT / "test_support/fixtures/xlsx"
SOURCE = "xlsx-shared-strings.xlsx"


def test_resumable_source_requires_explicit_lifetime() -> None:
    source = XlsxTextSource(FIXTURES / SOURCE)
    with pytest.raises(RuntimeError, match="not open"):
        iter(source)
    with source:
        next(iter(source))
        assert source.estimated_memory_bytes > 0
    with pytest.raises(RuntimeError, match="not open"):
        iter(source)
    with pytest.raises(RuntimeError, match="twice"):
        source.__enter__()
