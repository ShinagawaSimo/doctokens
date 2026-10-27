from unittest.mock import patch

from doctokens_excel import open_xlsx

from test_support.paths import REPO_ROOT

FIXTURES = REPO_ROOT / "test_support/fixtures"


def test_format_programs_are_compiled_per_code_and_owned_by_one_parse() -> None:
    from doctokens_excel.formatting.program import FormatProgram

    with patch("doctokens_excel.xlsx.parsing.modules.styles.index.FormatProgram", wraps=FormatProgram) as compiled:
        with open_xlsx(FIXTURES / "xlsx/xlsx-date-time.xlsx") as workbook:
            first_calls = compiled.call_count
            assert first_calls > 0
            keys = [call.args for call in compiled.call_args_list]
            assert len(keys) == len(set(keys))
            workbook.render(density="semantic")
            assert compiled.call_count == first_calls
        with open_xlsx(FIXTURES / "xlsx/xlsx-date-time.xlsx"):
            assert compiled.call_count == first_calls * 2
