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
  - First nonempty. DTX rich branch is selected only with nonempty display/fallback; inside it choose alt, display, fallback, cell text. Plain chooses image alt/display/[Image] or entity display/fallback/cell text.
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
  - Keep nonempty; XML alt is emitted only when imagePart/imageUrl is truthy.

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


## Source references

- [RichValueCatalog.from_package](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/features.py#L74)
- [RichValueCatalog.resolve](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/features.py#L132)
- [RichValueCatalog._parse_value](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/features.py#L195)
- [_append_cell_text](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L382)
