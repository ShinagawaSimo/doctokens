"""Manually update full-text goldens for Office files in fixtures/.

Run from the repository root:
    python test_support/update_goldens.py --only docx-list-decimal.docx
Omit --only to update every fixture. Review the resulting golden changes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    for package in ("ooxml_llm_core", "docx_llm_parser", "pptx_llm_parser", "xlsx_llm_parser"):
        sys.path.insert(0, str(ROOT / "packages" / package / "src"))

from docx_llm_parser import parse_docx  # noqa: E402
from pptx_llm_parser import parse_pptx  # noqa: E402
from xlsx_llm_parser import parse_xlsx  # noqa: E402

SUPPORT = ROOT / "test_support"
DENSITIES = ("semantic", "structural", "plain")
PARSERS = {"docx": parse_docx, "pptx": parse_pptx, "xlsx": parse_xlsx}


def discover_fixtures() -> list[Path]:
    return sorted(
        (
            path
            for format_name in PARSERS
            for path in (SUPPORT / "fixtures" / format_name).glob("*")
            if path.is_file() and path.suffix.lower() == f".{format_name}" and not path.name.startswith("~$")
        ),
        key=lambda path: path.as_posix().lower(),
    )


def golden_path(fixture: Path, density: str) -> Path:
    extension = "txt" if density == "plain" else "xml"
    return SUPPORT / "golden" / fixture.suffix[1:].lower() / f"{fixture.stem}.{density}.{extension}"


def parse_text(fixture: Path, density: str) -> str:
    return PARSERS[fixture.suffix[1:].lower()](fixture, density=density).text


def _write_golden(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text.encode("utf-8"))
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", metavar="FILE", help="fixture filename or stem; may be repeated")
    args = parser.parse_args(argv)
    fixtures = discover_fixtures()
    if not fixtures:
        parser.error("no Office fixtures found")
    if args.only:
        selected = set(args.only)
        known = {name for fixture in fixtures for name in (fixture.name, fixture.stem)}
        unknown = selected - known
        if unknown:
            parser.error(f"unknown fixture(s): {', '.join(sorted(unknown))}")
        fixtures = [fixture for fixture in fixtures if selected.intersection((fixture.name, fixture.stem))]

    # Validate selectors and finish parsing before changing any baseline.
    outputs = [(golden_path(fixture, density), parse_text(fixture, density)) for fixture in fixtures for density in DENSITIES]
    for target, text in outputs:
        _write_golden(target, text)
        print(f"UPDATED {target}")
    print(f"Updated {len(outputs)} golden file(s). Review them against Office before accepting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
