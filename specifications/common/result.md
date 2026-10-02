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
  - Body reads use the requested density. Resource explanations use semantic DTX; search and query use structural DTX.

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
  - Plain body: `doctokens-plain/1.0`; XML body and resource/search/query results: `doctokens-xml/1.0`.

### `media_type`

- **Output**
  - MIME type for text.

- **IR**
  - `ParseResult.media_type: str`

- **Parsing**
  - DTX: `application/xml`; DTP: `text/plain`.

### `to_dict()`

- **Output**
  - JSON-compatible dictionary containing all result fields, the report, and resource descriptors. `ResourceDescriptor.to_dict()` exports its public fields without bytes.

- **Parsing**
  - Creates a new dictionary; does not retain a package reader or serialize private format IR.


## Source references

- [ParseResult](../../packages/ooxml_llm_core/src/ooxml_llm_core/models.py#L75)
