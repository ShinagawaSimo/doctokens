# Charts

[DOCX](../README.md) / Charts

Both XML densities use the [shared bounded projection](../../common/chart.md#body-preview).
Names/categories are no longer duplicated at root. Plain uses the common
identity/title/type/count/name summary; complete resources retain full data.

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
  - Body/resource @points, the sum of per-series cached point counts.

- **OOXML**
  - Cached series arrays.

- **IR**
  - `Chart.pointCount: int`

- **Parsing**
  - Copy shared point_count.

### `series`

- **Output**
  - Bounded body series/point children; complete resource series details.

- **OOXML**
  - ChartML/ChartEx series.

- **IR**
  - `list[ChartSeries]`

- **Parsing**
  - Retain complete parsed series in the IR. The renderer applies the shared
    body budget independently of one-shot/session extraction. Complete arrays
    and annotations remain available through the resource API.

### `plots`

- **Output**
  - Resource combination-plot details.

- **OOXML**
  - ChartML plot children / ChartEx layoutId.

- **IR**
  - `list[ChartPlot]`

- **Parsing**
  - Retain shared ChartPlotInfo fields directly. Compact grouping/direction and
    axis ownership remain available in the bounded summary and full resources.

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


### `truncated`

- **Output**
  - `chart/@truncated="true"`.

- **OOXML**
  - Serializer policy.

- **IR**
  - Derived.

- **Parsing**
  - True only for an actual body preview omission; otherwise omitted.
