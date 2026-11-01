# Timelines

[XLSX](../README.md) / Timelines

Interactive-filter metadata is read without executing filters.

## Processing

Scan XML paths containing timeline; first timelineCacheDefinition/timeline descendant, fallback root. Multiple matching parts can produce multiple records.

## Fields

### `id`

- **Output**
  - timeline/@id.

- **OOXML**
  - Accepted matching XML part order.

- **IR**
  - `TimelineInfo.id: str`

- **Parsing**
  - timeline1,timeline2,...
- **Diagnostics**
  - Malformed timeline XML yields `XLSX_CATALOG_XML_INVALID` at the part and contributes no timeline record. Other catalog content remains available. See [optional catalog diagnostics](../workbook/catalog-diagnostics.md).

### `name`

- **Output**
  - timeline/@name.

- **OOXML**
  - Definition/@name.

- **IR**
  - `str`

- **Parsing**
  - Copy, default empty.

### `sourceName`

- **Output**
  - timeline/@source.

- **OOXML**
  - Definition/@sourceName.

- **IR**
  - `str`

- **Parsing**
  - Copy, default empty.

### `cache`

- **Output**
  - Structural/semantic timeline/@cache="cacheN" for a supported saved binding.

- **OOXML**
  - Definition/@pivotCacheId.

- **IR**
  - `TimelineInfo.cacheRef: str`.

- **Parsing**
  - Resolve a saved definition/@pivotCacheId using the
    [cache identity rules](cache.md#cacheid). Invalid, unknown and ambiguous
    declarations omit the link and emit XLSX_CATALOG_REFERENCE_UNRESOLVED.
    An absent optional binding is not guessed from names, field text or dates.
  - The target record occurs in the same XML response; no source number is
    serialized. Other timeline binding representations remain unsupported.

### `level`

- **Output**
  - timeline/@level.

- **OOXML**
  - First timelineState/timelineView/@level.

- **IR**
  - `str`

- **Parsing**
  - Copy nonempty.
