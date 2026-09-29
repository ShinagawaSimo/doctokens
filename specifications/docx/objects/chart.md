# Charts

[DOCX](../README.md) / Charts

The inline chart is a summary; full retained series are available to resource rendering.

## Processing

Series conversion: shared snake_case keys become DOCX camelCase keys. See [series](chart-series.md). Plot fields are defined in [plots](chart-plot.md).

## Fields

### `id`

- **Output**
  - `chart/@id`; chart resource key.

- **OOXML**
  - Chart relationship traversal.

- **IR**
  - `Chart.id: str`

- **Parsing**
  - chart1, chart2, ...; missing targets can leave gaps. Unresolved inline lookup uses rId as placeholder ID.

- **Diagnostics**
  - Missing/external target: `CHART_TARGET_MISSING`; read/parse failure: `CHART_PARSE_FAILED`.

### `chartType`

- **Output**
  - `chart/@type`.

- **OOXML**
  - ChartML/ChartEx plot family.

- **IR**
  - `Chart.chartType: str`

- **Parsing**
  - Map shared ChartInfo.chart_type; see [charts](../../common/chart.md).

### `title`

- **Output**
  - `chart/@title`.

- **OOXML**
  - Shared chart title, then drawing docPr title.

- **IR**
  - Optional `Chart.title: str`

- **Parsing**
  - Retain nonempty chart title; drawing common title can overwrite inline title.

### `seriesCount`

- **Output**
  - `chart/@series`.

- **OOXML**
  - Parsed series.

- **IR**
  - `Chart.seriesCount: int`

- **Parsing**
  - Copy shared series_count.

### `pointCount`

- **Output**
  - Resource summary; no inline DTX count.

- **OOXML**
  - Cached series arrays.

- **IR**
  - `Chart.pointCount: int`

- **Parsing**
  - Copy shared point_count.

### `series`

- **Output**
  - Inline names and up to 8 categories; resource series details.

- **OOXML**
  - ChartML/ChartEx series.

- **IR**
  - `list[ChartSeries]`

- **Parsing**
  - Map shared series fields as described below. Summary plan retains only index, pointCount, preview, optional name.

### `plots`

- **Output**
  - Resource combination-plot details.

- **OOXML**
  - ChartML plot children / ChartEx layoutId.

- **IR**
  - `list[ChartPlot]`

- **Parsing**
  - Shared index/chart_type/series_indices → index/chartType/seriesIndices. Removed by summary plan.

### `part`

- **Output**
  - Resource locator.

- **OOXML**
  - Resolved chart relationship.

- **IR**
  - `Chart.part: str`

- **Parsing**
  - Existing package part.

### `sourcePart`

- **Output**
  - Internal relation context.

- **OOXML**
  - Owning part.

- **IR**
  - `Chart.sourcePart: str`

- **Parsing**
  - Copy relationship source_part.

### `relationshipId`

- **Output**
  - Internal lookup key.

- **OOXML**
  - Relationship @Id.

- **IR**
  - `Chart.relationshipId: str`

- **Parsing**
  - Copy rId.

### `categories`

- **Output**
  - `chart/@categories`, comma-separated.

- **OOXML**
  - First series category cache.

- **IR**
  - `series[0].categories`

- **Parsing**
  - Join first 8 category strings; omit when empty. Summary-plan series omit categories.

### `names`

- **Output**
  - `chart/@names`, comma-separated.

- **OOXML**
  - Series names.

- **IR**
  - `series[*].name`

- **Parsing**
  - Join nonempty names in series order.

### `truncated`

- **Output**
  - `chart/@truncated="true"`.

- **OOXML**
  - Serializer policy.

- **IR**
  - Derived.

- **Parsing**
  - Always true for the inline summary; does not claim a particular number of omitted points.


## Source references

- [EmbeddedObjectExtractor._extract_charts](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/resources/objects.py#L76)
- [parse_chart_root](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/resources/objects.py#L188)
- [_chart_summary](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/resources/objects.py#L156)
- [_append_chart](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx_content.py#L18)
