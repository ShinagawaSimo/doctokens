# Pivot caches

[XLSX](../README.md) / Pivot caches

Caches supply field names and source metadata without refreshing records.

## Fields

### `id`

- **Output**
  - pivot-cache/@id.

- **OOXML**
  - Workbook pivotCache relationship enumeration.

- **IR**
  - `PivotCacheInfo.id: str`

- **Parsing**
  - cache1,cache2,...; failed catalog read still leaves a record with ID/cacheId/empty fields.
- **Diagnostics**
  - A declared missing cache target yields `XLSX_CATALOG_PART_MISSING`; malformed cache XML yields `XLSX_CATALOG_XML_INVALID`. The ID-only cache record remains. See [optional catalog diagnostics](../workbook/catalog-diagnostics.md).

### `cacheId`

- **Output**
  - pivot-cache/@cache-id.

- **OOXML**
  - workbook pivotCache/@cacheId.

- **IR**
  - `int`

- **Parsing**
  - int, missing/invalid0.

### `sourceRef`

- **Output**
  - pivot-cache/@ref.

- **OOXML**
  - worksheetSource/@ref.

- **IR**
  - `str`

- **Parsing**
  - Retain nonempty.

### `sourceSheet`

- **Output**
  - pivot-cache/@sheet.

- **OOXML**
  - worksheetSource/@sheet.

- **IR**
  - `str`

- **Parsing**
  - Retain nonempty.

### `fields`

- **Output**
  - Semantic pivot-cache/@fields.

- **OOXML**
  - cacheFields/cacheField/@name.

- **IR**
  - `list[str]`

- **Parsing**
  - Preserve order, empty default; join with comma.
- **Diagnostics**
  - Failed cache XML leaves this list empty and reports `XLSX_CATALOG_XML_INVALID` at the cache part.

### `refreshOnLoad`

- **Output**
  - pivot-cache/@refresh-on-load=true.

- **OOXML**
  - cache root/@refreshOnLoad.

- **IR**
  - `bool`

- **Parsing**
  - True for 1/true/True; does not trigger refresh.

### `recordCount`

- **Output**
  - Internal record count.

- **OOXML**
  - cache root/@recordCount.

- **IR**
  - `int`

- **Parsing**
  - int, missing/invalid0; cache records are not reconstructed.

### `slicerData`

- **Output**
  - Internal extension flag.

- **OOXML**
  - First descendant pivotCacheDefinition (excluding root)/@slicerData.

- **IR**
  - `bool`

- **Parsing**
  - True for 1/true/True.

### `timelineData`

- **Output**
  - Internal extension flag.

- **OOXML**
  - Same extension/@timelineData.

- **IR**
  - `bool`

- **Parsing**
  - True for 1/true/True.


## Source references

- [PivotCatalog.from_package](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/pivots.py#L32)
- [PivotCatalog._parse_cache](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/pivots.py#L83)
