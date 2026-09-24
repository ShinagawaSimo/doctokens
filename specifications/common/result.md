# ParseResult

[COMMON](README.md) / ParseResult

Public result of a parse, render, resource, search, or query operation.

## Fields

### `text`

- **Output**
  - Complete result text.

- **IR**
  - `ParseResult.text: str`

- **Parsing**
  - Serialize the selected content using the declared syntax. Diagnostics remain in `report`.

### `density`

- **Output**
  - Selected density.

- **IR**
  - `ParseResult.density: Density`

- **Parsing**
  - Read together with `syntax_version`; side operations can return legacy text even with a structural density.

### `selection`

- **Output**
  - Selection description.

- **IR**
  - `ParseResult.selection: dict[str, object]`

- **Parsing**
  - Format-specific `kind` and parameters describe all/page/slide/sheet/range/resource/search/query selection; not a completeness certificate.

### `report`

- **Output**
  - Diagnostic and orientation report.

- **IR**
  - `ParseResult.report: ParseReport`

- **Parsing**
  - References the parse report; a later window render retains already collected warnings.

### `resources`

- **Output**
  - Ordered resource descriptors, without bytes.

- **IR**
  - `ParseResult.resources: tuple[ResourceDescriptor, ...]`

- **Parsing**
  - DOCX/PPTX: assets, charts, SmartArt, then tables. XLSX: per sheet, images, charts, pivots, tables.

- **Absence and defaults**
  - Default constructor value: `()`.

### `syntax_version`

- **Output**
  - Text syntax identifier.

- **IR**
  - `ParseResult.syntax_version: str`

- **Parsing**
  - Main plain: `doctokens-plain/1.0`; main XML: `doctokens-xml/1.0`; explanatory side results: `legacy-markup/0`.

### `media_type`

- **Output**
  - MIME type for text.

- **IR**
  - `ParseResult.media_type: str`

- **Parsing**
  - DTX: `application/xml`; DTP and legacy side text: `text/plain`.


## Source references

- [ParseResult](../../packages/ooxml_llm_core/src/ooxml_llm_core/models.py#L75)
