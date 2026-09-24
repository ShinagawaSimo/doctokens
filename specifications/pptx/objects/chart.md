# Charts

[PPTX](../README.md) / Charts

Main output contains chart identity, family, and counts.

## Fields

### `id`

- **Output**
  - chart/@id.

- **OOXML**
  - Chart relationship index.

- **IR**
  - `ChartRecord.id` → `ShapeBlock.chartId`

- **Parsing**
  - chart1...; lazy-load referenced parts. Missing shape reference skips frame; missing relationship leaves placeholder.

- **Diagnostics**
  - CHART_MISSING_REF, CHART_MISSING_RID, CHART_ASSET_MISSING, CHART_PART_MISSING, CHART_PARSE_ERROR.

### `part`

- **Output**
  - Resource locator.

- **OOXML**
  - Resolved chart target.

- **IR**
  - `ChartRecord.part: str`

- **Parsing**
  - Existing internal chart part.

### `chart_type`

- **Output**
  - chart/@type.

- **OOXML**
  - Shared ChartInfo.chart_type.

- **IR**
  - `ChartRecord.chart_type` → `ShapeBlock.chartType`

- **Parsing**
  - Copy [shared chart fields](../../common/chart.md).

### `title`

- **Output**
  - Resource title; no inline chart title attribute.

- **OOXML**
  - Shared ChartInfo.title.

- **IR**
  - `ChartRecord.title: str`

- **Parsing**
  - Retain resource value; not copied to shape.

### `series_count`

- **Output**
  - chart/@series.

- **OOXML**
  - Shared count.

- **IR**
  - `ChartRecord.series_count` → `ShapeBlock.seriesCount`

- **Parsing**
  - Copy including zero.

### `point_count`

- **Output**
  - chart/@points.

- **OOXML**
  - Shared count.

- **IR**
  - `ChartRecord.point_count` → `ShapeBlock.pointCount`

- **Parsing**
  - Copy including zero.

### `series`

- **Output**
  - Resource data.

- **OOXML**
  - Shared series caches.

- **IR**
  - `list[ChartSeriesInfo]`

- **Parsing**
  - [Series](../../common/chart-series.md); retain snake_case fields.

### `plots`

- **Output**
  - Resource combination plots.

- **OOXML**
  - Shared plot records.

- **IR**
  - `list[ChartPlotInfo]`

- **Parsing**
  - [Plots](../../common/chart-plot.md).

### `truncated`

- **Output**
  - chart/@truncated=true.

- **OOXML**
  - Serialization policy.

- **IR**
  - Derived.

- **Parsing**
  - Always true for inline summary.


## Source references

- [EmbeddedObjectExtractor._load_chart](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/resources/objects.py#L166)
- [SlideParser._chart_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L596)
- [_append_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L54)
