# Chart plots

[DOCX](../README.md) / Chart plots

DOCX chart records retain shared ChartPlotInfo without a second field-name map.
The [common plot definition](../../common/chart-plot.md) defines source indices,
grouping, direction, explicit axis IDs, membership and unreadable-family markers.

## Fields

### `plots`

- **Output**
  - plot children in structural/semantic body previews and full chart resources.
- **IR**
  - Chart.plots and InlineObject.plots: list[ChartPlotInfo].
- **Parsing**
  - Keep combination plots and plots whose explicit grouping/axis references
    distinguish their reading meaning. The series' plotIndex references the
    plot index; it is not a guessed primary/secondary assignment.
  - Full resources retain all plots and annotations. Existing body previews
    retain at most eight series and eight points per series; associated labels
    and saved trendlines follow the same bounded reading policy.
