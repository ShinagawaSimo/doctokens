from pathlib import Path

import pytest
from doctokens_word import open_docx

FIXTURES = Path(__file__).resolve().parents[3] / "test_support/fixtures"


def test_search_never_searches_generated_xml_and_checks_session_lifetime() -> None:
    session = open_docx(FIXTURES / "docx/docx-paragraph.docx")
    with session:
        assert not session.find_text("<document").matches
        assert not session.find_text(".*").matches  # A literal query, never a regex wildcard.
        with pytest.raises(ValueError):
            session.find_text("")
    with pytest.raises(RuntimeError, match="not open"):
        session.find_text("paragraph")
