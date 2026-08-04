"""Smoke test: verify the core package is importable."""

import unittest


class CoreImportTests(unittest.TestCase):
    def test_version_is_available(self) -> None:
        from ooxml_llm_core import __version__

        self.assertTrue(__version__)


if __name__ == "__main__":
    unittest.main()
