"""Protect manual baseline selection and writing; no Office content is synthesized."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from test_support import update_goldens as updater

ROOT_TAGS = {"docx": "document", "pptx": "presentation", "xlsx": "workbook"}


@pytest.fixture
def fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    monkeypatch.setattr(updater, "SUPPORT", tmp_path)
    paths = []
    for format_name in updater.PARSERS:
        path = tmp_path / "fixtures" / format_name / f"{format_name}-sample.{format_name}"
        path.parent.mkdir(parents=True)
        path.touch()  # Only a discovery placeholder; stub parsers below never read Office bytes.
        (path.parent / f"~${path.name}").touch()
        (path.parent / "asset.png").touch()
        paths.append(path)

    def stub_parser(format_name: str):
        def parse(source: Path, *, density: str) -> SimpleNamespace:
            if density == "plain":
                return SimpleNamespace(text=f"{source.name}: {density}\r\n中文 & < >\n")
            return SimpleNamespace(text=f'<{ROOT_TAGS[format_name]} format="{format_name}"/>')

        return parse

    monkeypatch.setattr(updater, "PARSERS", {format_name: stub_parser(format_name) for format_name in updater.PARSERS})
    return paths


def test_selected_update_preserves_other_baselines(fixtures: list[Path]) -> None:
    for fixture in fixtures:
        for density in updater.DENSITIES:
            golden = updater.golden_path(fixture, density)
            golden.parent.mkdir(parents=True, exist_ok=True)
            golden.write_bytes(b"reviewed")
    assert updater.main(["--only", fixtures[1].name]) == 0
    for fixture in fixtures:
        for density in updater.DENSITIES:
            raw = (
                f'<{ROOT_TAGS[fixture.suffix[1:]]} format="{fixture.suffix[1:]}"/>'
                if density != "plain"
                else f"{fixture.name}: {density}\r\n中文 & < >\n"
            )
            expected = updater.golden_text(raw, density).encode()
            expected = expected if fixture == fixtures[1] else b"reviewed"
            assert updater.golden_path(fixture, density).read_bytes() == expected
    assert not list(updater.SUPPORT.rglob("*.tmp"))


def test_xml_goldens_are_pretty_printed_without_changing_inline_text() -> None:
    source = '<document format="docx"><p>Before<b>bold</b>After</p></document>'
    assert updater.format_xml(source) == '<document format="docx">\n  <p>Before<b>bold</b>After</p>\n</document>\n'


def test_unknown_selector_changes_nothing(fixtures: list[Path]) -> None:
    golden = updater.golden_path(fixtures[0], "semantic")
    golden.parent.mkdir(parents=True)
    golden.write_bytes(b"reviewed")
    with pytest.raises(SystemExit) as error:
        updater.main(["--only", fixtures[0].name, "--only", "misspelled.docx"])
    assert error.value.code == 2
    assert list((updater.SUPPORT / "golden").rglob("*.*")) == [golden]
    assert golden.read_bytes() == b"reviewed"


def test_parse_failure_does_not_partially_update(fixtures: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:
    golden = updater.golden_path(fixtures[0], "semantic")
    golden.parent.mkdir(parents=True)
    golden.write_bytes(b"reviewed")

    def parse(source: Path, density: str) -> str:
        if density == "plain":
            raise ValueError("parse failed")
        return '<document format="docx"/>'

    monkeypatch.setattr(updater, "parse_text", parse)
    with pytest.raises(ValueError, match="parse failed"):
        updater.main(["--only", fixtures[0].stem])
    assert golden.read_bytes() == b"reviewed"
    assert list((updater.SUPPORT / "golden").rglob("*.*")) == [golden]


def test_all_formats_are_discovered_without_assets_or_office_lock_files(fixtures: list[Path]) -> None:
    assert updater.discover_fixtures() == fixtures
    assert updater.main([]) == 0
    goldens = list((updater.SUPPORT / "golden").rglob("*.*"))
    assert len(goldens) == 9
    assert {path.suffix for path in goldens} == {".xml", ".txt"}
