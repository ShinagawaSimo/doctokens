"""Rebuild the Office fixture matrix and regenerate its existing goldens.

Run from the repository root:

    python test_support/update_docx_goldens.py

The fixture directories are the source of truth. The script scans the current
DOCX, PPTX, and XLSX files, rewrites ``test_support/fixture_matrix.json``, and
updates three goldens for every materialized fixture.

Use ``--only`` with a fixture id or filename to update only selected goldens.
The matrix is still rebuilt from every file currently on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages" / "ooxml_llm_core" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "docx_llm_parser" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "pptx_llm_parser" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "xlsx_llm_parser" / "src"))

from docx_llm_parser import Density as DocxDensity  # noqa: E402
from docx_llm_parser import parse_docx  # noqa: E402
from pptx_llm_parser import Density as PptxDensity  # noqa: E402
from pptx_llm_parser import parse_pptx  # noqa: E402
from test_support.file_contract import write_text_result  # noqa: E402
from xlsx_llm_parser import parse_xlsx  # noqa: E402


TEST_SUPPORT = ROOT / "test_support"
MATRIX_PATH = TEST_SUPPORT / "fixture_matrix.json"
_PACKAGE_EXTENSIONS = {"docx": ".docx", "pptx": ".pptx", "xlsx": ".xlsx"}
_DENSITIES = ("semantic", "structural", "plain")
_GOLDEN_SUFFIXES = (".semantic.html", ".structural.html", ".plain.txt")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        action="append",
        metavar="CASE",
        help="update goldens for a fixture id or filename; may be repeated",
    )
    return parser.parse_args()


def _case_id(package: str, fixture: Path) -> str:
    prefix = f"{package}-"
    return fixture.stem[len(prefix) :] if fixture.stem.startswith(prefix) else fixture.stem


def _case(package: str, fixture: Path) -> dict[str, Any]:
    stem = fixture.stem
    return {
        "id": _case_id(package, fixture),
        "fixture": f"fixtures/{package}/{fixture.name}",
        "golden": [
            f"golden/{package}/{stem}.semantic.html",
            f"golden/{package}/{stem}.structural.html",
            f"golden/{package}/{stem}.plain.txt",
        ],
    }


def _build_matrix() -> dict[str, Any]:
    packages: dict[str, list[dict[str, Any]]] = {}
    for package, extension in _PACKAGE_EXTENSIONS.items():
        fixture_dir = TEST_SUPPORT / "fixtures" / package
        fixtures = sorted(
            (
                path
                for path in fixture_dir.glob(f"*{extension}")
                if path.is_file() and not path.name.startswith("~$")
            ),
            key=lambda path: path.name.lower(),
        )
        packages[package] = [_case(package, fixture) for fixture in fixtures]
    return {
        "version": 1,
        "description": "One Office file per atomic parser feature. Paths are relative to test_support.",
        "packages": packages,
    }


def _selected(case: dict[str, Any], selected: set[str]) -> bool:
    if not selected:
        return True
    fixture_name = Path(str(case["fixture"])).name
    return str(case["id"]) in selected or fixture_name in selected


def _parse(package: str, fixture: Path, density: str) -> str:
    if package == "docx":
        result = parse_docx(fixture, density=DocxDensity(density))
    elif package == "pptx":
        result = parse_pptx(fixture, density=PptxDensity(density))
    elif package == "xlsx":
        result = parse_xlsx(fixture, density=density)
    else:
        raise ValueError(f"Unsupported fixture package: {package}")
    if not isinstance(result, str):
        raise TypeError(f"Expected a materialized result for {fixture.name}, got {type(result).__name__}")
    return result


def _golden_paths(matrix: dict[str, Any]) -> set[Path]:
    return {TEST_SUPPORT / str(golden) for cases in matrix["packages"].values() for case in cases for golden in case["golden"]}


def _remove_stale_goldens(matrix: dict[str, Any]) -> int:
    expected = _golden_paths(matrix)
    removed = 0
    for package in _PACKAGE_EXTENSIONS:
        golden_dir = TEST_SUPPORT / "golden" / package
        if not golden_dir.exists():
            continue
        for path in golden_dir.iterdir():
            if path.is_file() and path.name.endswith(_GOLDEN_SUFFIXES) and path not in expected:
                path.unlink()
                removed += 1
                print(f"REMOVED {path.relative_to(ROOT)}")
    return removed


def main() -> int:
    args = _arguments()
    selected = set(args.only or [])
    matrix = _build_matrix()
    matrix_text = json.dumps(matrix, ensure_ascii=False, indent=2) + "\n"
    MATRIX_PATH.write_bytes(matrix_text.encode("utf-8"))
    removed = _remove_stale_goldens(matrix)

    updated = 0
    for package, cases in matrix["packages"].items():
        for case in cases:
            if not _selected(case, selected):
                continue
            fixture = TEST_SUPPORT / str(case["fixture"])
            for density, golden_name in zip(_DENSITIES, case["golden"], strict=True):
                golden = TEST_SUPPORT / str(golden_name)
                write_text_result(_parse(package, fixture, density), golden)
                updated += 1
                print(f"UPDATED {golden.relative_to(ROOT)}")

    if selected and updated == 0:
        print(f"No matching fixture for: {', '.join(sorted(selected))}", file=sys.stderr)
        return 1

    case_count = sum(len(cases) for cases in matrix["packages"].values())
    print(f"WROTE {MATRIX_PATH.relative_to(ROOT)} ({case_count} fixture(s))")
    print(f"Done: updated {updated} golden file(s), removed {removed} stale golden file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
