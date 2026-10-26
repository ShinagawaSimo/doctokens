from weakref import ref

from doctokens_core.containers.opc.limits import PackageLimits
from doctokens_core.containers.opc.reader import PackageReader

from test_support.paths import REPO_ROOT

FIXTURES = REPO_ROOT / "test_support/fixtures"


def test_consumed_worksheet_rows_are_released_before_the_scan_ends() -> None:
    # This checks live XML ownership, not parsed cell content. A short native
    # worksheet lets the parser read ahead while its parent tree remains alive.
    from doctokens_excel.xlsx.parsing.modules.worksheets.sheet_types import NS_S
    from doctokens_excel.xlsx.parsing.modules.worksheets.xml_stream import iter_sheet_elements

    with (
        PackageReader(FIXTURES / "xlsx/xlsx-shared-strings.xlsx", PackageLimits()) as package,
        package.open_entry("xl/worksheets/sheet1.xml") as stream,
    ):
        elements = iter_sheet_elements(stream)
        first = next(element for element in elements if element.tag == f"{{{NS_S}}}row")
        consumed = ref(first)
        del first
        next(element for element in elements if element.tag == f"{{{NS_S}}}row")
        assert consumed() is None
        elements.close()
