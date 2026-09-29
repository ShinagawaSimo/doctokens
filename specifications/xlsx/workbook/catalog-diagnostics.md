# Optional catalog diagnostics

[XLSX](../README.md) / Workbook / Optional catalog diagnostics

Rich values, cell controls, pivot caches and tables, slicers, and timelines use optional XML parts. Their parsing failures preserve independently readable cells and catalog entries. An absent optional feature with no reference to it produces no catalog warning. Package-level errors, including limits and invalid package paths, retain their normal failure behavior.

## Warning fields

### `XLSX_FORMULA_BAR_UNAVAILABLE`

- **Output**
  - `ParseWarning.code = "XLSX_FORMULA_BAR_UNAVAILABLE"`; `locator` is the worksheet part and cell reference.
- **OOXML**
  - A non-formula numeric cell has a display format whose formula-bar edit value cannot be reconstructed from the stored value, effective XF, date system, and explicit locale alone.
- **IR**
  - The cell keeps its formatted `text`, omits `raw`, and does not copy the cached `<v>` value into the formula-bar field.
- **Parsing**
  - Dates, times, percentages, scientific notation, locale-specific numbering, and unsupported custom sections may produce this warning. A formula cell does not produce this warning for its cache; it uses `formula` and the cache is only used for display.

### `XLSX_CATALOG_XML_INVALID`

- **Output**
  - `ParseWarning.code = "XLSX_CATALOG_XML_INVALID"`; `locator` is the optional XML part name.
- **OOXML**
  - A discovered optional catalog XML part that raises `xml.etree.ElementTree.ParseError`.
- **IR**
  - No catalog record is inferred from the failed part. Independently parsed records remain available.
- **Parsing**
  - The failure is confined to the affected catalog part. Its cell display fallback, if any, remains available. Index failures caused solely by this unreadable part do not add repeated reference warnings.

### `XLSX_CATALOG_PART_MISSING`

- **Output**
  - `ParseWarning.code = "XLSX_CATALOG_PART_MISSING"`; `locator` is the missing target part. The message identifies the source and, when available, the relationship ID.
- **OOXML**
  - A declared pivot-table/cache or rich-image relationship target that is absent from the package; a rich relationship part required by used `r:id` slots; or `xl/metadata.xml` required by a selected cell's `@vm`.
- **IR**
  - No value is fabricated for the missing target; existing cell values and available metadata remain.
- **Parsing**
  - A missing part is reported only when a supported feature uses its declaration or reference. Repeated uses of the same missing part within a catalog produce one warning.

### `XLSX_CATALOG_RELS_INVALID`

- **Output**
  - `ParseWarning.code = "XLSX_CATALOG_RELS_INVALID"`; `locator` is the affected `.rels` part.
- **OOXML**
  - An optional rich-value or web-image relationship part with malformed XML or invalid required relationship attributes.
- **IR**
  - No relationship target is resolved from that part; unrelated rich descriptors and cell values remain.
- **Parsing**
  - XML parse errors and relationship decoding `KeyError`/`ValueError` are confined to the optional relationship part. A broken relationship part does not generate an additional unresolved warning for each of its IDs.

### `XLSX_CATALOG_REFERENCE_UNRESOLVED`

- **Output**
  - `ParseWarning.code = "XLSX_CATALOG_REFERENCE_UNRESOLVED"`; `locator` is the XML part containing the unresolved reference. The message identifies its index or relationship ID.
- **OOXML**
  - A used `valueMetadata` index, rich-image or web-image `r:id`, cell-style `xfComplement` mapping, or workbook pivot-cache relationship that cannot resolve against an otherwise readable catalog.
- **IR**
  - The unsupported descriptor is omitted or retains its existing fallback; ordinary cell values remain.
- **Parsing**
  - The warning is deduplicated by code, locator, and reference within the catalog read. References in unrecognized extensions are not interpreted as supported catalog references.

## Source references

- [_CatalogParts](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/catalog_parts.py#L38)
- [RichValueCatalog](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/rich_values.py#L28)
- [CellControlCatalog](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/features.py#L23)
- [PivotCatalog](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/pivots.py#L22)
