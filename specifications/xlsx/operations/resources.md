# Resource operations

[XLSX](../README.md) / Resource operations

XLSX resources come from drawing and table metadata in the parsed scope.

## Resource-only catalog

### `XlsxResourceCatalog(source, options=...)`

- **Output**
  - Context-managed `resources` tuple and `read_resource("image", resource_id)`
    returning original bytes. No cell rendering or query methods are exposed.
- **Source**
  - Workbook/sheet relationships, drawing/chart, table and pivot metadata.
- **Processing**
  - Use the resource parse plan and the same global source order and resource
    numbering as a full workbook session. Skip worksheet XML, shared strings,
    styles, rich-cell catalogs and cell IR. Directory discovery does not validate
    unrelated cell parts or replace a complete parse report.
  - The catalog owns its package reader. Exit/close releases it; later access
    fails. Normal package limits and resource access restrictions still apply.
    The Agent tool caches descriptors per immutable snapshot and closes the
    temporary catalog; an image read reopens the resource plan, without cells.

## Fields

### `kind`

- **Output**
  - Bytes or explanatory ParseResult.

- **Source**
  - Resource directory.

- **IR**
  - `str`

- **Parsing**
  - Binary: drawing image only. Explanatory: chart, pivot_table. Tables are query sources; render_resource does not handle table.

### `resource_id`

- **Output**
  - Exact resource key.

- **Source**
  - ResourceDescriptor.id.

- **IR**
  - `str`

- **Parsing**
  - Unknown ID/render kind → KeyError. Binary unsupported kind → ValueError; missing readable part → ValueError.

### `text`

- **Output**
  - Resource result string.

- **Source**
  - Chart/PivotTable IR.

- **IR**
  - `ParseResult.text`

- **Parsing**
  - Complete `<workbook density="semantic" format="xlsx"><resources>OBJECT</resources></workbook>` with `syntax_version=doctokens-xml/1.0`, `media_type=application/xml`, `density=semantic`.
  - Chart retains chart/series/point records. Pivot summary uses a closed `pivot-table` with quoted `id` and `name` attributes. XML attributes and text are escaped by the shared serializer.
