# Timelines

[XLSX](../README.md) / Timelines

Interactive-filter metadata is read without executing filters.

## Processing

Scan XML paths containing timeline; first timelineCacheDefinition/timeline descendant, fallback root. Multiple matching parts can produce multiple records. Catalog XML failures caught by _parse_part are skipped without an added diagnostic.

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

### `cacheId`

- **Output**
  - Internal; no timeline cache attribute.

- **OOXML**
  - Definition/@pivotCacheId.

- **IR**
  - `int`

- **Parsing**
  - Nonempty → int; invalid0.

### `level`

- **Output**
  - timeline/@level.

- **OOXML**
  - First timelineState/timelineView/@level.

- **IR**
  - `str`

- **Parsing**
  - Copy nonempty.


## Source references

- [PivotCatalog._parse_timelines](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/features.py#L510)
- [_append_pivot_context](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L212)
