"""Package-level catalogs for modern Excel features.

The worksheet scanner consumes these catalogs while it is already walking the
cell XML.  Keeping the indirection resolution here prevents every cell or
renderer from reopening metadata, richData, styles, or pivot parts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.package import PackageReader

from ....models import (
    CellControl,
)
from .catalog_parts import _CatalogParts, _int, _local_name, _part_names


@dataclass
class CellControlCatalog:
    """Resolve Excel feature-property bags into style-indexed cell controls."""

    by_style: dict[int, CellControl] = field(default_factory=dict)

    @classmethod
    def from_package(cls, pkg: PackageReader, *, warnings: list[ParseWarning]) -> CellControlCatalog:
        parts = _CatalogParts(pkg, warnings)
        roots: list[ET.Element] = []
        for part in _part_names(pkg):
            lower = part.lower()
            if lower.endswith(".xml") and (lower.endswith("styles.xml") or "featurepropertybag" in lower):
                root = parts.xml(part)
                if root is not None:
                    roots.append(root)
        bags: list[ET.Element] = [
            node
            for root in roots
            for node in root.iter()
            if _local_name(node.tag) in {"bag", "featurePropertyBag"} and node.get("type")
        ]
        values = [cls._bag_values(bag) for bag in bags]
        checkbox_by_index: dict[int, CellControl] = {}
        for index, (bag, props) in enumerate(zip(bags, values, strict=True)):
            if bag.get("type") == "Checkbox":
                checkbox_by_index[index] = {"kind": "checkbox", "default": _int(props.get("default"), 0)}
        controls_by_index: dict[int, CellControl] = {}
        for index, (bag, props) in enumerate(zip(bags, values, strict=True)):
            if bag.get("type") != "XFControls":
                continue
            checkbox_index = _int(props.get("CellControl"), -1)
            if checkbox_index in checkbox_by_index:
                controls_by_index[index] = checkbox_by_index[checkbox_index]

        mapped_complements: list[int] = []
        for bag, props in zip(bags, values, strict=True):
            if bag.get("type") == "XFComplements":
                mapped_complements.extend(_int(item, -1) for item in props.get("MappedFeaturePropertyBags", "").split(","))

        style_to_complement: dict[int, int] = {}
        for root in roots:
            cell_xfs = next((node for node in root.iter() if _local_name(node.tag) == "cellXfs"), None)
            if cell_xfs is None:
                continue
            for style_index, xf in enumerate(cell_xfs):
                marker = next((node for node in xf.iter() if _local_name(node.tag) == "xfComplement"), None)
                if marker is not None:
                    style_to_complement[style_index] = _int(marker.get("i"), -1)
        if style_to_complement and not bags and not any("featurepropertybag" in part.lower() for part in parts.failed_parts):
            for complement_index in sorted(set(style_to_complement.values())):
                parts.reference_missing("xl/styles.xml", f"xfComplement i={complement_index}")
        result: dict[int, CellControl] = {}
        for style_index, complement_index in style_to_complement.items():
            if 0 <= complement_index < len(mapped_complements):
                bag_index = mapped_complements[complement_index]
                if 0 <= bag_index < len(bags) and bags[bag_index].get("type") == "XFComplement":
                    controls_index = _int(values[bag_index].get("XFControls"), -1)
                    if controls_index in controls_by_index:
                        result[style_index] = controls_by_index[controls_index]
        return cls(result)

    @staticmethod
    def _bag_values(bag: ET.Element) -> dict[str, str]:
        values: dict[str, str] = {}
        for child in bag:
            key = child.get("k")
            if not key:
                continue
            text = (child.text or "").strip()
            if _local_name(child.tag) == "a":
                text = ",".join((item.text or "").strip() for item in child)
            values[key] = text
        return values
