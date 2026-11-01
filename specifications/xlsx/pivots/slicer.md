# Slicers

[XLSX](../README.md) / Slicers

Interactive-filter metadata is read without executing filters.

## Processing

Scan XML paths containing slicercache; first slicerCacheDefinition descendant, fallback root.

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
- **Diagnostics**
  - Malformed slicer-cache XML yields `XLSX_CATALOG_XML_INVALID` at the part and contributes no slicer record. Other caches remain available. See [optional catalog diagnostics](../workbook/catalog-diagnostics.md).

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

### `cache`

- **Output**
  - Structural/semantic slicer/@cache="cacheN" when uniquely resolved.

- **OOXML**
  - tabularSlicerCache or olapSlicerCache/@pivotCacheId.

- **IR**
  - `SlicerInfo.cacheRef: str`.

- **Parsing**
  - A saved pivotCacheId uses the [cache identity rules](cache.md#cacheid).
    Invalid, unknown or ambiguous keys omit the link and produce
    XLSX_CATALOG_REFERENCE_UNRESOLVED. An absent optional binding adds no link
    or warning; table slicers and unsupported binding encodings are not guessed.
  - The compact link targets a pivot-cache in the same XML result. Source
    numeric keys are discarded after resolution.

### `type`

- **Output**
  - Internal kind.

- **OOXML**
  - Catalog kind.

- **IR**
  - `str`

- **Parsing**
  - Always slicer.
