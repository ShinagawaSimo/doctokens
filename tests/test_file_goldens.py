"""Compare manually authored Office fixtures with their reviewed full output."""

from pathlib import Path

import pytest

from test_support.update_goldens import DENSITIES, discover_fixtures, golden_path, parse_text


@pytest.mark.parametrize("fixture", discover_fixtures(), ids=lambda path: path.name)
@pytest.mark.parametrize("density", DENSITIES)
def test_file_matches_golden(fixture: Path, density: str) -> None:
    golden = golden_path(fixture, density)
    assert golden.is_file(), (
        f'Missing golden: {golden}\nGenerate it manually with: python test_support/update_goldens.py --only "{fixture.name}"'
    )
    # Decode bytes directly so CRLF, trailing whitespace and final newlines are compared exactly.
    assert parse_text(fixture, density) == golden.read_bytes().decode("utf-8")
