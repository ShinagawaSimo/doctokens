"""Search option validation, independent of document content."""

import pytest
from doctokens_core.text.search import TextSearchOptions


@pytest.mark.parametrize(
    "options",
    [{"offset": -1}, {"limit": 0}, {"limit": 201}, {"context_before": -1}, {"context_after": 4001}, {"case_sensitive": "true"}],
)
def test_search_options_reject_invalid_budgets(options: dict) -> None:
    with pytest.raises(ValueError):
        TextSearchOptions(**options)
