# Pivot tables

[XLSX](../README.md) / Pivot tables

Pivot output describes declared layout and source fields.

## Fields

### `id`

- **Output**
  - pivot-table/@id; resource key.

- **OOXML**
  - Worksheet pivotTable relationship order.

- **IR**
  - `PivotTableInfo.id: str`

- **Parsing**
  - pivot1,pivot2,...; unresolved catalog still produces an ID-only placeholder.
- **Diagnostics**
  - A declared missing table target yields `XLSX_CATALOG_PART_MISSING`; malformed table XML yields `XLSX_CATALOG_XML_INVALID`. The relationship-based ID placeholder remains. See [optional catalog diagnostics](../workbook/catalog-diagnostics.md).

### `name`

- **Output**
  - pivot-table/@name.

- **OOXML**
  - pivotTableDefinition/@name.

- **IR**
  - `str`

- **Parsing**
  - Copy, default empty.

### `ref`

- **Output**
  - pivot-table/@ref.

- **OOXML**
  - First location/@ref.

- **IR**
  - `str`

- **Parsing**
  - Retain nonempty.

### `cacheId`

- **Output**
  - Internal cache identity.

- **OOXML**
  - pivotTableDefinition/@cacheId.

- **IR**
  - `int`

- **Parsing**
  - int, default 0; lookup cache catalog.

### `sourceRef`

- **Output**
  - pivot-table/@source-ref.

- **OOXML**
  - Resolved cache sourceRef.

- **IR**
  - `str`

- **Parsing**
  - Copy if present.

### `sourceSheet`

- **Output**
  - pivot-table/@source-sheet.

- **OOXML**
  - Resolved cache sourceSheet.

- **IR**
  - `str`

- **Parsing**
  - Copy if present.

### `fieldNames`

- **Output**
  - Internal name lookup.

- **OOXML**
  - Resolved cache fields.

- **IR**
  - `list[str]`

- **Parsing**
  - Copy cache list.

### `rowFields`

- **Output**
  - Semantic @rows.

- **OOXML**
  - rowFields/field/@x.

- **IR**
  - `list[str]`

- **Parsing**
  - Resolve int index against fieldNames; out-of-range/default-1 → decimal index string.
- **Diagnostics**
  - If the referenced cache XML is unreadable, fallback index strings remain and `XLSX_CATALOG_XML_INVALID` identifies that cache part.

### `columnFields`

- **Output**
  - Semantic @columns.

- **OOXML**
  - colFields/field/@x.

- **IR**
  - `list[str]`

- **Parsing**
  - Same index resolution.

### `pageFields`

- **Output**
  - Semantic @pages.

- **OOXML**
  - pageFields/field/@x.

- **IR**
  - `list[str]`

- **Parsing**
  - Same path expects child local-name field. Conventional pageField/@fld is not read by this branch.

### `dataFields`

- **Output**
  - Semantic @values.

- **OOXML**
  - dataFields/dataField/@name, fallback @fld.

- **IR**
  - `list[str]`

- **Parsing**
  - Copy source label/index strings; comma join.

### `filters`

- **Output**
  - Semantic @filters.

- **OOXML**
  - filters descendant filter/@name, fallback @fld.

- **IR**
  - `list[str]`

- **Parsing**
  - Copy labels/index strings; conditions are not evaluated.

### `style`

- **Output**
  - Internal style name.

- **OOXML**
  - pivotTableStyleInfo/@name.

- **IR**
  - `str`

- **Parsing**
  - Copy nonempty; no current DTX attribute.


## Source references

- [PivotCatalog._parse_table](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/pivots.py#L111)
- [PivotCatalog.tables_for_relationships](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/pivots.py#L64)
- [_append_sheet_metadata](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx_metadata.py#L31)
