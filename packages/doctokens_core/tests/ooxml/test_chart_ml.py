"""Invalid values and incomplete chart parts are exceptional producer input."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from doctokens_core.ooxml.charts.parser import ChartParser
from doctokens_core.ooxml.charts.values import (
    _first_dimension,
    _namespace,
    _safe_int,
    _summary_chart_type,
    _to_float,
    _true_value,
)


class ChartParserTests(unittest.TestCase):
    def test_chart_helpers_and_empty_chart_paths(self) -> None:
        self.assertEqual(ChartParser().parse(ET.Element("chartSpace"))["chart_type"], "unknown")
        self.assertEqual(_summary_chart_type([]), "unknown")
        self.assertIsNone(_safe_int("bad"))
        self.assertIsNone(_to_float("bad"))
        self.assertFalse(_true_value(None))
        self.assertIsNone(_namespace("plain"))
        self.assertEqual(_first_dimension({}), [])


if __name__ == "__main__":
    unittest.main()
