"""Native data-table selections and malformed master declarations."""

import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from xlsx_llm_parser import open_xlsx, parse_xlsx

FIXTURE = Path(__file__).resolve().parents[3] / "test_support/fixtures/xlsx/xlsx-formula-data-table.xlsx"
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
SHEET_PART = "xl/worksheets/sheet1.xml"


@pytest.mark.parametrize("density", ["structural", "semantic"])
def test_selection_without_master_retains_group_in_one_shot_and_session(density: str) -> None:
    selected = parse_xlsx(FIXTURE, density=density, sheet="Sheet1", range_spec="D3:D3")
    with open_xlsx(FIXTURE) as session:
        full_before = session.render(density=density).text
        assert session.render(density=density, sheet="Sheet1", range_spec="D3:D3").text == selected.text
        # Render-time compaction must not erase formula membership from session IR.
        assert session.render(density=density).text == full_before
        assert session.render(density=density, sheet="Sheet1", range_spec="D3:D3").text == selected.text
    root = ET.fromstring(selected.text)
    grid = root.find(".//grid")
    assert grid is not None and grid.get("ref") == "D3:D3"
    cells = root.findall(".//cell")
    assert len(cells) == 1
    assert cells[0].attrib == {
        "formula": "TABLE(,B1)",
        "formula-type": "dataTable",
        "formula-range": "D2:D3",
    }
    assert cells[0].text == "8"
    assert not selected.report.warnings


def _malformed_master(attributes: dict[str, str | None], *, conflicting_formula: bool = False) -> bytes:
    """Damage a copy of the native fixture, never replace the Office workbook."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(FIXTURE) as source, zipfile.ZipFile(buffer, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == SHEET_PART:
                root = ET.fromstring(data)
                master = root.find(f".//{{{MAIN}}}c[@r='D2']/{{{MAIN}}}f")
                assert master is not None
                for name, value in attributes.items():
                    if value is None:
                        master.attrib.pop(name, None)
                    else:
                        master.set(name, value)
                if conflicting_formula:
                    dependent = root.find(f".//{{{MAIN}}}c[@r='D3']")
                    assert dependent is not None
                    ET.SubElement(dependent, f"{{{MAIN}}}f").text = "1+7"
                data = ET.tostring(root)
            target.writestr(info, data)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("attributes", "selection", "value"),
    [
        ({"r1": None}, "D3:D3", "8"),
        ({"r1": "B0"}, "D3:D3", "8"),
        ({"r1": "XFE1"}, "D3:D3", "8"),
        ({"dt2D": "yes"}, "D3:D3", "8"),
        ({"dtr": "yes"}, "D3:D3", "8"),
        ({"del1": "yes"}, "D3:D3", "8"),
        ({"dt2D": "1", "r2": None}, "D3:D3", "8"),
        ({"ref": None}, "D2:D2", "6"),
        ({"ref": "D2:"}, "D2:D2", "6"),
        ({"ref": "D3:D2"}, "D2:D2", "6"),
        ({"ref": "C2:D3"}, "D2:D2", "6"),
        ({"ref": "D2:XFE3"}, "D2:D2", "6"),
    ],
)
def test_invalid_declaration_preserves_cache_without_inventing_formula(
    attributes: dict[str, str | None], selection: str, value: str
) -> None:
    result = parse_xlsx(_malformed_master(attributes), density="semantic", sheet="Sheet1", range_spec=selection)
    cell = ET.fromstring(result.text).find(".//cell")
    assert cell is not None and cell.text == value
    assert cell.get("formula") is None
    assert cell.get("raw") is None
    assert cell.get("formula-type") == "dataTable"
    assert [(warning.code, warning.locator) for warning in result.report.warnings] == [
        ("DATA_TABLE_FORMULA_INVALID", f"{SHEET_PART}!{selection.split(':')[0]}")
    ]


def test_invalid_unselected_table_does_not_warn() -> None:
    result = parse_xlsx(_malformed_master({"r1": None}), density="semantic", sheet="Sheet1", range_spec="B1:B1")
    assert not result.report.warnings
    assert "dataTable" not in result.text


def test_conflicting_formula_is_not_overwritten() -> None:
    result = parse_xlsx(_malformed_master({}, conflicting_formula=True), density="semantic", sheet="Sheet1", range_spec="D3:D3")
    cell = ET.fromstring(result.text).find(".//cell")
    assert cell is not None and cell.get("formula") == "1+7" and cell.text == "8"
    assert cell.get("formula-type") is None
    assert [warning.code for warning in result.report.warnings] == ["DATA_TABLE_FORMULA_INVALID"]
