"""Execute every materialized atomic Office case through its public parser API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from test_support.api_v2_text import Density as DocxDensity
from test_support.api_v2_text import Density as PptxDensity
from test_support.api_v2_text import parse_docx, parse_pptx, parse_xlsx
from test_support.file_contract import assert_text_matches_golden, output_path, write_text_result

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / "test_support" / "fixture_matrix.json"
_DENSITIES = ("semantic", "structural", "plain")


def _cases() -> list[Any]:
    matrix: dict[str, Any] = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    strict = bool(os.environ.get("OOXML_REQUIRE_REAL_FIXTURES"))
    return [
        pytest.param(package, case, id=f"{package}-{case['id']}")
        for package, cases in matrix["packages"].items()
        for case in cases
        if strict or (ROOT / "test_support" / case["fixture"]).exists()
    ]


@pytest.mark.parametrize(("package", "case"), _cases())
def test_materialized_case_matches_standalone_goldens(package: str, case: dict[str, Any]) -> None:
    fixture = ROOT / "test_support" / case["fixture"]
    if not fixture.exists():
        message = f"real fixture is not materialized: {fixture}"
        if os.environ.get("OOXML_REQUIRE_REAL_FIXTURES"):
            pytest.fail(message)
        pytest.skip(message)

    for density, golden_name in zip(_DENSITIES, case["golden"], strict=True):
        golden = ROOT / "test_support" / golden_name
        actual = output_path(package, f"matrix-{case['id']}", golden.name)
        write_text_result(_parse(package, fixture, density), actual)
        assert_text_matches_golden(actual, golden)


def _parse(package: str, fixture: Path, density: str) -> str | Any:
    if package == "docx":
        return parse_docx(fixture, density=DocxDensity(density))
    if package == "pptx":
        return parse_pptx(fixture, density=PptxDensity(density))
    if package == "xlsx":
        return parse_xlsx(fixture, density=density)
    raise AssertionError(f"unsupported package in fixture matrix: {package}")
