"""Validate the standalone real-file/golden inventory without embedding expectations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from ooxml_llm_core.chart_ml import _CHART_TYPE_MAP

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / "test_support" / "fixture_matrix.json"
KNOWN_PACKAGES = {"docx", "pptx", "xlsx"}
CHART_EX_TYPES = {"boxwhisker", "funnel", "histogram", "pareto", "sunburst", "treemap", "waterfall"}


def test_fixture_matrix_has_unique_atomic_cases_and_safe_paths() -> None:
    matrix = _load_matrix()
    assert matrix["version"] == 1
    packages = matrix["packages"]
    assert set(packages) == KNOWN_PACKAGES

    for package, cases in packages.items():
        ids: set[str] = set()
        for case in cases:
            case_id = case["id"]
            assert case_id not in ids, f"duplicate {package} case id: {case_id}"
            ids.add(case_id)

            fixture = _resolve(case["fixture"])
            golden = [_resolve(path) for path in case["golden"]]
            assert fixture.is_relative_to(ROOT / "test_support" / "fixtures" / package)
            assert fixture.suffix.lower() in {".docx", ".pptx", ".xlsx"}
            assert len(golden) == 3
            assert all(path.is_relative_to(ROOT / "test_support" / "golden" / package) for path in golden)
            assert [path.name.rsplit(".", 2)[-2] for path in golden] == ["semantic", "structural", "plain"]

        legacy_types = {chart_type.lower() for chart_type in _CHART_TYPE_MAP.values()}
        required_chart_cases = {f"chart-{chart_type}" for chart_type in legacy_types | CHART_EX_TYPES}
        required_chart_cases.add("chart-combination")
        assert required_chart_cases <= ids, f"{package} is missing supported chart file cases"


def test_fixture_matrix_reports_missing_manual_files() -> None:
    matrix = _load_matrix()
    missing: list[str] = []
    for package, cases in matrix["packages"].items():
        for case in cases:
            fixture = _resolve(case["fixture"])
            if not fixture.exists():
                missing.append(f"{package}/{case['id']}: fixture={fixture.relative_to(ROOT)}")
                continue
            missing.extend(
                f"{package}/{case['id']}: golden={golden}" for golden in case["golden"] if not _resolve(golden).exists()
            )

    if missing and os.environ.get("OOXML_REQUIRE_REAL_FIXTURES"):
        pytest.fail("Missing real-file cases or golden files:\n" + "\n".join(missing))


def _load_matrix() -> dict[str, Any]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _resolve(relative: str) -> Path:
    path = (ROOT / "test_support" / relative).resolve()
    assert path.is_relative_to(ROOT / "test_support"), f"path escapes test_support: {relative}"
    return path
