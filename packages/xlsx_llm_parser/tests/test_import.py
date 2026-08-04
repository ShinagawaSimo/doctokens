"""Smoke test: verify xlsx parser package is importable."""

import unittest


class XlsxImportTests(unittest.TestCase):
    def test_version_is_available(self) -> None:
        from xlsx_llm_parser import __version__

        self.assertTrue(__version__)


if __name__ == "__main__":
    unittest.main()
