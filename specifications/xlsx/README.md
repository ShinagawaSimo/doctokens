# XLSX reference

[Reference](../README.md) / XLSX

SpreadsheetML retains stored cell values, formula text, and worksheet structure. Parsing does not calculate formulas or refresh external data. Worksheet grids remain sparse.

## Interface

- [Parsing and selection](api.md)
- [Output profile](output.md)
- [Parse manifest](manifest.md)

## Workbook

- [Sheets](workbook/sheet.md)
- [Defined names](workbook/defined-name.md)
- [External workbook references](workbook/external-link.md)

## Cell grid

- [Rows](cells/row.md)
- [Cells](cells/cell.md)
- [Grid projection](cells/grid.md)
- [Merged cells](cells/merge.md)
- [Cell hyperlinks](cells/hyperlink.md)

## Formulas

- [Formula text](cells/formula.md)
- [Shared formulas](cells/shared-formula.md)
- [Array formulas and spills](cells/array-formula.md)

## Cell values

- [Shared strings](cells/shared-string.md)
- [Rich text runs](cells/rich-text.md)
- [Rich values](cells/rich-value.md)
- [Cell controls](cells/control.md)

## Styles

- [Display number formats](styles/number-format.md)
- [Cell styles](styles/style.md)
- [Spreadsheet colors](styles/color.md)
- [Style ranges](styles/style-range.md)

## Annotations

- [Cell notes](annotations/comment.md)
- [Threaded comments](annotations/threaded-comment.md)
- [Comment mentions](annotations/mention.md)

## Sheet rules

- [AutoFilter](rules/filter.md)
- [Data validation](rules/validation.md)
- [Conditional formatting](rules/conditional-format.md)
- [Conditional visual formats](rules/visual-format.md)

## Objects

- [Declared tables](objects/table.md)
- [Drawing anchors](objects/drawing.md)
- [Drawing images](objects/image.md)
- [Drawing charts](objects/chart.md)
- [Chart series](objects/chart-series.md)
- [Chart points](objects/chart-point.md)

## Pivot data

- [Pivot caches](pivots/cache.md)
- [Pivot tables](pivots/table.md)
- [Slicers](pivots/slicer.md)
- [Timelines](pivots/timeline.md)

## Search, query, and resource operations

- [Cell search](operations/search.md)
- [Tabular queries](operations/query.md)
- [Query columns](operations/column.md)
- [Query conditions](operations/condition.md)
- [Query aggregates](operations/aggregate.md)
- [Query ordering](operations/order.md)
- [Resource operations](operations/resources.md)
