# Drawing charts

[XLSX](../README.md) / Drawing charts

Chart summaries attach to the worksheet independently of grid truncation.

## Fields

### `id`

- **Output**
  - chart/@id.

- **OOXML**
  - Resolvable chart reference with supported relation type.

- **IR**
  - `DrawingChart.id: str`

- **Parsing**
  - chart1,chart2,... across sheets.

### `ref`

- **Output**
  - chart/@ref.

- **OOXML**
  - Drawing start anchor.

- **IR**
  - `str`

- **Parsing**
  - See [anchors](drawing.md).

### `type`

- **Output**
  - chart/@type.

- **OOXML**
  - Shared chart_type.

- **IR**
  - `str`

- **Parsing**
  - Copy; failed part leaves empty type, which is an explicit empty attribute.

### `title`

- **Output**
  - chart/@title.

- **OOXML**
  - Shared title.

- **IR**
  - `str`

- **Parsing**
  - Copy if nonempty; initial empty string retained otherwise.

### `series_count`

- **Output**
  - chart/@series.

- **OOXML**
  - Shared series_count.

- **IR**
  - `int`

- **Parsing**
  - Default 0.

### `part`

- **Output**
  - Resource chart part.

- **OOXML**
  - Resolved chart relation.

- **IR**
  - `str`

- **Parsing**
  - Missing → CHART_PART_MISSING; read/parse exception → CHART_XML_INVALID; retain placeholder summary.

### `series`

- **Output**
  - Resource series; inline @names.

- **OOXML**
  - Shared series caches.

- **IR**
  - `list[DrawingChartSeries]`

- **Parsing**
  - See [series](chart-series.md); names are nonempty names joined with comma.

### `plotTypes`

- **Output**
  - chart/@plots.

- **OOXML**
  - Shared combination plots.

- **IR**
  - `list[str]`

- **Parsing**
  - Copy families in plot order only for combination charts.

### `truncated`

- **Output**
  - chart/@truncated=true.

- **OOXML**
  - Inline summary policy.

- **IR**
  - Derived.

- **Parsing**
  - Always true.


## Source references

- [_parse_chart_part](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/drawings.py#L142)
- [_append_sheet_metadata](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx_metadata.py#L31)
