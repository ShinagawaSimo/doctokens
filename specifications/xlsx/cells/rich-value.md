# Rich values

[XLSX](../README.md) / Rich values

Rich metadata resolves saved entity/image descriptors without retrieving external data.

## Processing

Cell vm resolves valueMetadata records in xl/metadata.xml through futureMetadata[name=XLRICHVALUE]/rvb/@i. Positive vm tries index-1 then index; zero tries 0. Rich parts are found by supported basenames, not a single fixed path. Structure index comes from rv/@s. An image slot is the first key containing ImageIdentifier or beginning _rvRel:, fallback first v/value with kind rel/r. WebImageIdentifier can supply a target; a later valid relation slot can overwrite the same target kind.

## Fields

### `type`

- **Output**
  - cell/@rich-type.

- **OOXML**
  - rv/@t, fallback structure/@t.

- **IR**
  - `RichCellValue.type: str`

- **Parsing**
  - Default rich.
- **Diagnostics**
  - Invalid `xl/richData/*.xml` part syntax yields `XLSX_CATALOG_XML_INVALID`; the saved cell value remains available. See [optional catalog diagnostics](../workbook/catalog-diagnostics.md).

### `fields`

- **Output**
  - Internal named saved values.

- **OOXML**
  - rv children v/value; structure child k/key @n/@name.

- **IR**
  - `dict[str,str]`

- **Parsing**
  - Assign keys by position; excess values use valueN (0-based). Duplicate keys overwrite.

### `fallback`

- **Output**
  - Readable fallback text.

- **OOXML**
  - rv/fb.

- **IR**
  - `str`

- **Parsing**
  - Join itertext and strip; omit empty.

### `display`

- **Output**
  - Preferred rich value text.

- **OOXML**
  - fields _DisplayString, Text, Display; fallback.

- **IR**
  - `str`

- **Parsing**
  - Image descriptions/display candidates skip whitespace-only values and
    preserve meaningful spacing. Bound image reading uses alt/display/fallback
    under its existing contract. Unbound images retain the cached cell value
    (or saved display/fallback when no cached text exists), the independent alt
    attribute and an unsupported image child. Plain includes an unavailable
    image marker and description, followed by a distinct nonempty saved value.
    This avoids replacing a saved error with a caption. Entity-value behavior
    remains display/fallback/cell text.
- **Diagnostics**
  - A used `s:c/@vm` with no `xl/metadata.xml` yields `XLSX_CATALOG_PART_MISSING`. A readable binding that points outside the rich-value list yields `XLSX_CATALOG_REFERENCE_UNRESOLVED`. An invalid metadata or rich-value XML part yields `XLSX_CATALOG_XML_INVALID`. The cached `s:v` text remains available.

### `imagePart`

- **Output**
  - cell/@in-cell-image=true; internal binary locator.

- **OOXML**
  - Image relation slot or web-image address.

- **IR**
  - `str`

- **Parsing**
  - Use resolved internal target; no automatic resource-directory entry for this in-cell image.
- **Diagnostics**
  - A missing declared binary target yields `XLSX_CATALOG_PART_MISSING`. An invalid rich relationship part yields `XLSX_CATALOG_RELS_INVALID`; an unresolved used `r:id` in a readable relationship part yields `XLSX_CATALOG_REFERENCE_UNRESOLVED`. No image target is inferred on those paths.

### `imageUrl`

- **Output**
  - cell/@in-cell-image=true; internal external locator.

- **OOXML**
  - External image relation slot / web-image address.

- **IR**
  - `str`

- **Parsing**
  - Copy external target; no download or XML URL attribute.
- **Diagnostics**
  - Invalid optional relationship XML yields `XLSX_CATALOG_RELS_INVALID`; an unresolved used ID in valid relationship XML yields `XLSX_CATALOG_REFERENCE_UNRESOLVED`.

### `alt`

- **Output**
  - cell/@alt and preferred image text.

- **OOXML**
  - fields Text, fallback AltText.

- **IR**
  - `str`

- **Parsing**
  - Prefer non-whitespace Text, then AltText; preserve meaningful source spacing.
    Both XML densities retain it for a recognized image value even when its
    binary/URL binding is absent. Do not use source filenames or indices.

### `imageStatus`

- **Output**
  - Recognized image values set cell/@in-cell-image=true independently of source
    binding. Unbound images add `<unsupported type="image"/>` and retain alt.
    Plain uses `[Image unavailable: description]` (or `[Image unavailable]`)
    and retains a distinct saved value such as #VALUE!.
- **Source**
  - Known image rich-value types or declared ImageIdentifier/_rvRel keys, after
    resolving saved image relationships. A cell error alone does not imply image.
- **IR**
  - `RichCellValue.imageStatus: Literal["bound", "unbound"]`.
- **Parsing**
  - Bound means a saved embedded source or external URI was resolved; external
    sources are not downloaded. Missing parts/relationships remain unbound.
    No image resource-directory entry or fake binary ID is introduced here.
- **Diagnostics**
  - Existing catalog failures remain the primary diagnostic. An unresolved image
    source adds XLSX_CATALOG_REFERENCE_UNRESOLVED only when source decoding has
    not already diagnosed the catalog problem. Reading projections do not append
    duplicate diagnostics; resource registration remains a separate capability.

### `sizing`

- **Output**
  - Internal image sizing mode.

- **OOXML**
  - fields ImageSizing.

- **IR**
  - `int`

- **Parsing**
  - int(value), failure 0; omit empty source.

### `width`

- **Output**
  - Internal image width.

- **OOXML**
  - fields ImageWidth.

- **IR**
  - `str`

- **Parsing**
  - Keep nonempty source string.

### `height`

- **Output**
  - Internal image height.

- **OOXML**
  - fields ImageHeight.

- **IR**
  - `str`

- **Parsing**
  - Keep nonempty source string.

### `computed`

- **Output**
  - Internal computed-image flag.

- **OOXML**
  - fields ComputedImage.

- **IR**
  - `bool`

- **Parsing**
  - True exactly for "1" in image descriptor path.

### `decorative`

- **Output**
  - Internal decorative-image flag.

- **OOXML**
  - fields CalcOrigin.

- **IR**
  - `bool`

- **Parsing**
  - True exactly for "6" in image descriptor path.

### `warning`

- **Output**
  - No output.

- **OOXML**
  - No current assignment.

- **IR**
  - Declared optional str.

- **Parsing**
  - `_parse_value` does not assign this per-value IR member. Catalog failures are emitted as parse-report warnings, not stored in `RichCellValue.warning`.
