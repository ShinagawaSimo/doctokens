# Resource operations

[XLSX](../README.md) / Resource operations

XLSX resources come from drawing and table metadata in the parsed scope.

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


## Source references

- [XlsxReadSession.read_resource](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/api.py)
- [XlsxReadSession.render_resource](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/api.py)
- [_render_chart_resource](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/_resources.py)
