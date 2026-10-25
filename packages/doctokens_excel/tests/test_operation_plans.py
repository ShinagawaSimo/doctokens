"""Work budgets and malformed-tail handling on native workbooks."""

import io
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from doctokens_excel import find_xlsx_cells, open_xlsx, parse_xlsx, query_xlsx
from doctokens_excel.parsing.modules.worksheets.cells import _parse_cell
from doctokens_excel.parsing.modules.worksheets.scanner import parse_sheet

FIXTURES = Path(__file__).resolve().parents[3] / "test_support/fixtures/xlsx"


@pytest.mark.parametrize(
    "extra,expected_data_refs",
    [({}, ["A2"]), ({"where": [{"column": "C", "op": "gt", "value": 0}]}, ["A2", "C2"])],
)
def test_query_projects_dependencies_before_converting_cells(extra: dict, expected_data_refs: list[str]) -> None:
    source = FIXTURES / "xlsx-formula-horizontal.xlsx"
    args = {"sheet": "Sheet1", "range_spec": "A1:C2", "header_row": 1, "select": ["A"], "limit": 1, **extra}
    with open_xlsx(source) as session:
        expected = session.query_data(**args).text
    with patch("doctokens_excel.parsing.modules.worksheets.scanner._parse_cell", wraps=_parse_cell) as converted:
        assert query_xlsx(source, **args).text == expected
        # Complete native header identities remain available, but only output
        # and filter columns are converted for data rows.
        refs = [call.args[5] for call in converted.call_args_list]
        assert refs == ["A1", "B1", "C1", *expected_data_refs]


def test_query_does_not_scan_other_worksheets() -> None:
    source = FIXTURES / "xlsx-formula-cross-sheet.xlsx"
    with patch("doctokens_excel._operation_source.parse_sheet", wraps=parse_sheet) as scanned:
        query_xlsx(source, sheet="Data", range_spec="A1:A2", header_row=1)
        assert scanned.call_count == 2  # Header/tail declarations, followed by value rows.
        assert len({call.args[1] for call in scanned.call_args_list}) == 1


@pytest.mark.parametrize("kind", ["formula", "comment", "hyperlink", "definedName"])
def test_field_search_skips_shared_strings_styles_and_nonmatching_cell_projections(kind: str) -> None:
    source = FIXTURES / "xlsx-formula-horizontal.xlsx"
    with open_xlsx(source) as session:
        expected = session.find_cells("2", kind=kind).text
    with (
        patch("doctokens_excel.parsing.runner._parse_shared_strings", side_effect=AssertionError("strings loaded")),
        patch("doctokens_excel.parsing.runner.parse_styles", side_effect=AssertionError("styles loaded")),
        patch("doctokens_excel.parsing.modules.worksheets.scanner._parse_cell", wraps=_parse_cell) as converted,
    ):
        assert find_xlsx_cells(source, "2", kind=kind).text == expected
        refs = [call.args[5] for call in converted.call_args_list]
        assert refs == (["A1", "B1", "C1"] if kind == "formula" else [])


def test_limited_query_validates_trailing_xml_and_releases_the_reader() -> None:
    # A corrupt tail cannot be saved by Office; damage a private copy of a
    # native file rather than manufacturing ordinary document content.
    source = io.BytesIO()
    with ZipFile(FIXTURES / "xlsx-shared-strings.xlsx") as original, ZipFile(source, "w") as damaged:
        for entry in original.infolist():
            value = original.read(entry.filename)
            if entry.filename == "xl/worksheets/sheet1.xml":
                value += b"<broken"
            damaged.writestr(entry, value)
    from doctokens_core.package import PackageReader

    close = PackageReader.__exit__
    with patch.object(PackageReader, "__exit__", autospec=True, side_effect=close) as closed:
        with pytest.raises(ET.ParseError):
            query_xlsx(source.getvalue(), sheet="Sheet1", range_spec="A1:A3", header_row=1, limit=1)
        assert closed.call_count == 1


def test_selective_shared_strings_still_validate_the_xml_tail() -> None:
    # Office cannot save a corrupt XML tail. Damage only this exceptional
    # condition in a private copy of an existing native shared-string file.
    source = io.BytesIO()
    with ZipFile(FIXTURES / "xlsx-shared-strings.xlsx") as original, ZipFile(source, "w") as damaged:
        for entry in original.infolist():
            value = original.read(entry.filename)
            if entry.filename == "xl/sharedStrings.xml":
                value += b"<broken"
            damaged.writestr(entry, value)
    with (
        patch("doctokens_excel.parsing.modules.worksheets.preview._CELL_BUDGET", 1),
        patch("doctokens_excel.rendering.window._CELL_BUDGET", 1),
        pytest.raises(ET.ParseError),
    ):
        parse_xlsx(source.getvalue(), sheet="Sheet1")
