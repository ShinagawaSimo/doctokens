"""Resolve saved XLDAPR cell metadata without inferring array calculation results."""

from __future__ import annotations

from dataclasses import dataclass, field

from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.contracts.models import ParseWarning

from .catalog_parts import NS_R, _CatalogParts
from .metadata import NS_S

_S = f"{{{NS_S}}}"
_DYNAMIC = "{http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray}dynamicArrayProperties"


@dataclass(slots=True)
class DynamicArrayCatalog:
    bindings: list[bool | None] = field(default_factory=list)
    parts: _CatalogParts | None = None

    @classmethod
    def from_package(
        cls,
        package: PackageReader,
        warnings: list[ParseWarning],
        *,
        parts: _CatalogParts | None = None,
    ) -> DynamicArrayCatalog:
        parts = parts if parts is not None else _CatalogParts(package, warnings)
        relationship = next(
            (r for r in parts.relationships("xl/workbook.xml").values() if r.type == f"{NS_R}/sheetMetadata"),
            None,
        )
        part = relationship.resolved_target if relationship else "xl/metadata.xml" if package.exists("xl/metadata.xml") else None
        if part is None:
            return cls(parts=parts)
        root = parts.xml(part, source="xl/workbook.xml")
        if root is None:
            return cls(parts=parts)
        if root.tag != _S + "metadata":
            parts.warn("DYNAMIC_ARRAY_METADATA_UNRESOLVED", part, "root", f"Unsupported cell metadata root: {root.tag}")
            return cls(parts=parts)
        types = root.find(_S + "metadataTypes")
        dynamic_types = {
            index for index, node in enumerate(types if types is not None else (), 1) if node.get("name") == "XLDAPR"
        }
        future = next((node for node in root.findall(_S + "futureMetadata") if node.get("name") == "XLDAPR"), None)
        future_records = list(future.findall(_S + "bk")) if future is not None else []
        metadata = root.find(_S + "cellMetadata")
        bindings: list[bool | None] = []
        type_count = len(types) if types is not None else 0
        for book in metadata.findall(_S + "bk") if metadata is not None else ():
            state = False
            invalid = False
            for record in book.findall(_S + "rc"):
                try:
                    type_index, value_index = int(record.get("t", "")), int(record.get("v", ""))
                except ValueError:
                    invalid = True
                    continue
                if not 1 <= type_index <= type_count:
                    invalid = True
                    continue
                if type_index not in dynamic_types:
                    continue
                if not 0 <= value_index < len(future_records):
                    invalid = True
                    continue
                properties = next(future_records[value_index].iter(_DYNAMIC), None)
                if properties is None or properties.get("fDynamic", "0") not in {"0", "1", "true", "false"}:
                    invalid = True
                elif properties.get("fDynamic", "0") in {"1", "true"}:
                    state = True
            bindings.append(None if invalid else state)
        return cls(bindings, parts)

    def is_dynamic(self, cm: str | None, locator: str) -> bool:
        if cm is None or cm == "0":
            return False
        try:
            index = int(cm) - 1
        except ValueError:
            index = -1
        if 0 <= index < len(self.bindings) and self.bindings[index] is not None:
            return bool(self.bindings[index])
        if self.parts is not None:
            self.parts.warn(
                "DYNAMIC_ARRAY_METADATA_UNRESOLVED",
                locator,
                f"cm={cm}",
                f"Cell metadata index {cm!r} cannot establish a dynamic array",
            )
        return False
