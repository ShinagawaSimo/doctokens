"""Validation contracts for public API inputs."""

from __future__ import annotations

import unittest

from pptx_llm_parser import Density, ResourceType


class PublicApiValidationTests(unittest.TestCase):
    def test_string_enums_preserve_serialized_values(self) -> None:
        self.assertEqual(str(Density.SEMANTIC), "semantic")
        self.assertEqual(str(Density.STRUCTURAL), "structural")
        self.assertEqual(str(Density.PLAIN), "plain")
        self.assertEqual(str(ResourceType.TABLES), "tables")
        self.assertEqual(str(ResourceType.MEDIAS), "medias")

    def test_density_rejects_unknown_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "density"):
            Density.parse("typo")

    def test_resource_type_rejects_unknown_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown resource type"):
            ResourceType.parse("unknown")

    def test_resource_type_plural_flags(self) -> None:
        self.assertTrue(ResourceType.IMAGES.is_plural)
        self.assertTrue(ResourceType.CHARTS.is_plural)
        self.assertTrue(ResourceType.SMARTARTS.is_plural)
        self.assertTrue(ResourceType.TABLES.is_plural)
        self.assertTrue(ResourceType.MEDIAS.is_plural)
        self.assertFalse(ResourceType.IMAGE.is_plural)
        self.assertFalse(ResourceType.MEDIA.is_plural)


if __name__ == "__main__":
    unittest.main()
