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

### `cache`

- **Output**
  - Structural/semantic pivot-table/@cache="cacheN" when uniquely resolved.

- **OOXML**
  - pivotTableDefinition/@cacheId.

- **IR**
  - `PivotTableInfo.cacheRef: str`.

- **Parsing**
  - Resolve the source unsigned cacheId through the workbook cache catalog,
    following its [identity rules](cache.md#cacheid). Do not expose the source
    number or infer an absent value as zero. An unknown or ambiguous key omits
    the link and emits XLSX_CATALOG_REFERENCE_UNRESOLVED.
  - The target pivot-cache record occurs in the same XML response, including
    selected ranges. Source sheet/range fields remain readable on the table.
    A failed cache part can still have an addressable summary with diagnostics.

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
