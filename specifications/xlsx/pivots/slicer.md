# Slicers

[XLSX](../README.md) / Slicers

Interactive-filter metadata is read without executing filters.

## Processing

Scan XML paths containing slicercache; first slicerCacheDefinition descendant, fallback root. Catalog XML failures caught by _parse_part are skipped without an added diagnostic.

## Fields

### `id`

- **Output**
  - slicer/@id.

- **OOXML**
  - Accepted matching XML part order.

- **IR**
  - `SlicerInfo.id: str`

- **Parsing**
  - slicer1,slicer2,...

### `name`

- **Output**
  - slicer/@name.

- **OOXML**
  - Definition/@name.

- **IR**
  - `str`

- **Parsing**
  - Copy, default empty.

### `sourceName`

- **Output**
  - slicer/@source.

- **OOXML**
  - Definition/@sourceName.

- **IR**
  - `str`

- **Parsing**
  - Copy, default empty.

### `cacheId`

- **Output**
  - slicer/@cache-id.

- **OOXML**
  - tabularSlicerCache or olapSlicerCache/@pivotCacheId.

- **IR**
  - `int`

- **Parsing**
  - Nonempty → int; invalid0.

### `type`

- **Output**
  - Internal kind.

- **OOXML**
  - Catalog kind.

- **IR**
  - `str`

- **Parsing**
  - Always slicer.


## Source references

- [PivotCatalog._parse_slicers](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/features.py#L482)
- [_append_pivot_context](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L212)
