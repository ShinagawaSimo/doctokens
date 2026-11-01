# Drawing charts

[XLSX](../README.md) / Drawing charts

Both XML densities use the [shared bounded projection](../../common/chart.md#body-preview),
including per-series cached point previews. Names and plot-type lists are no
longer duplicated at root. Plain uses the common compact identity/title/type/
count/name summary; complete resources retain full data.

Chart summaries attach to worksheets and chart sheets independently of grid
truncation, using the same saved chart decoder and complete resource reader.

Explicit grouping/direction/axis references appear as compact plot children in
both XML body densities. Full resources retain custom point labels, saved
trendline text/configuration and explicit series axis relationships as defined
in [shared series semantics](../../common/chart-series.md). The body remains a
compact series summary and does not expand to all points or annotations.

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
  - Missing → CHART_PART_MISSING; invalid XML/value/required structure →
    CHART_XML_INVALID. Retain the chart identity and add
    `<unsupported type="chart"/>` in the body and full resource. Unknown chart
    type also remains marked unreadable with CHART_TYPE_UNSUPPORTED;
    plain adds `[Unparsed chart]`.

### `series`

- **Output**
  - Bounded body series/point children; complete resource series.

- **OOXML**
  - Shared saved literal points, reference caches, or ChartEx dimensions.

- **IR**
  - `list[DrawingChartSeries]`

- **Parsing**
  - See [series](chart-series.md). Body names occur on the corresponding series.

### `axes`

- **Output**
  - Axis child elements in structural/semantic worksheet chart summaries and complete chart resources. Plain summaries retain their existing compact chart text.
- **OOXML**
  - Shared ChartML plotArea catAx/valAx/dateAx/serAx records.
- **IR**
  - `DrawingChart.axes: list[dict[str, str]]`.
- **Parsing**
  - Carry the complete parsed axes from the chart-part result into its attached drawing-chart record. Use the shared short IDs and closed reading projection for cross-axis relationships, titles, non-General formats, explicit bounds/reversal/log base and units. Omit absent fields and axis data when none is saved.
  - Example: a value-axis title USD, display unit thousands and bounds 0..100 produce `<axis display-unit="thousands" kind="valAx" maximum="100" minimum="0" title="USD"/>` with a chart-local axisN identity under the shared field definitions.
  - Units/scales describe the source axis. Do not divide the saved point values by the display factor, infer unsaved bounds, or substitute the axis title for an absent chart title. See [shared axes](../../common/chart.md#axes).

### `truncated`

- **Output**
  - chart/@truncated=true.

- **OOXML**
  - Inline summary policy.

- **IR**
  - Derived.

- **Parsing**
  - True only for actual body preview omissions; otherwise omitted.
