# Pivot caches

[XLSX](../README.md) / Pivot caches

Caches supply field names and source metadata without refreshing records.

## Fields

### `id`

- **Output**
  - Structural/semantic pivot-cache/@id; referenced by pivot-table, slicer and
    supported timeline @cache. This is a local XML target, not a binary or
    render_resource cache resource.

- **OOXML**
  - Workbook pivotCache relationship enumeration.

- **IR**
  - `PivotCacheInfo.id: str`

- **Parsing**
  - cache1,cache2,... in resolvable workbook relationship order. A failed cache
    part still leaves a record with its compact ID and empty fields; callers
    may refer to that record while diagnostics describe its unreadable content.
- **Diagnostics**
  - A declared missing cache target yields `XLSX_CATALOG_PART_MISSING`; malformed cache XML yields `XLSX_CATALOG_XML_INVALID`. The ID-only cache record remains. See [optional catalog diagnostics](../workbook/catalog-diagnostics.md).

### `cacheId`

- **Output**
  - No public source-number attribute. Only the compact id is serialized.

- **OOXML**
  - workbook pivotCache/@cacheId.

- **IR**
  - Temporary parser lookup key, absent from the reading model.

- **Parsing**
  - Require a readable unsigned 32-bit integer (including valid zero); XML
    whitespace and a leading plus are accepted. Missing, invalid, negative and
    oversized values do not default to zero. Duplicate source numbers are
    ambiguous, even if their parts coincide; no consumer is linked through them.
  - Keep readable cache records independently of source-key validity. A unique
    valid key maps consumers to the record's compact ID; unresolved relations
    do not fabricate a cache target. Selected ranges retain caches and bound
    slicer/timeline metadata required by selected pivot tables.
- **Diagnostics**
  - XLSX_CATALOG_REFERENCE_UNRESOLVED identifies missing/invalid/ambiguous keys
    and consumers of unknown keys. Diagnostics are collected during parsing,
    not repeated on each render.

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
