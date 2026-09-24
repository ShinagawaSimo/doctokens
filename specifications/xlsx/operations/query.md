# Tabular queries

[XLSX](../README.md) / Tabular queries

query_data operates on saved display values with a finite set of tabular operations.

## Processing

Source → typed row materialization → where → group/aggregate → select → order → limit. Display strings containing a dot attempt float(), otherwise int(); failures remain strings. Percent/date/formatted strings are not normalized back to raw numbers. Missing cells remain missing dictionary keys; hidden/shadow cells are not excluded.

## Fields

### `table_id`

- **Output**
  - Query source table.

- **Source**
  - Declared table ID.

- **IR**
  - `str | None`

- **Parsing**
  - When supplied, find table, use declared columns/range, and skip its first range row as header; takes precedence over sheet/range/header options. Unknown → ValueError.

### `sheet`

- **Output**
  - Explicit query source.

- **Source**
  - Sheet display name.

- **IR**
  - `str | None`

- **Parsing**
  - Used only with range_spec and header_row when no table_id.

### `range_spec`

- **Output**
  - Inclusive input range.

- **Source**
  - Call argument.

- **IR**
  - `str | None`

- **Parsing**
  - Requires colon A1:B2; no synthetic source rows.

### `header_row`

- **Output**
  - Header source row.

- **Source**
  - Call argument.

- **IR**
  - `int | None`

- **Parsing**
  - Explicit source requires it. Strip source text for labels; omit all rows <=header_row. Missing header produces no declared columns; cells can still materialize under __colN keys.

### `select`

- **Output**
  - Output columns.

- **Source**
  - Column names/keys/letters.

- **IR**
  - `list[str] | None`

- **Parsing**
  - Applied after grouping only when result_rows is nonempty; preserve requested order.

### `where`

- **Output**
  - Row predicates.

- **Source**
  - Call argument.

- **IR**
  - `list[WhereCondition]`

- **Parsing**
  - All predicates must match; see [conditions](condition.md).

### `group_by`

- **Output**
  - Grouping keys.

- **Source**
  - Column selectors.

- **IR**
  - `list[str]`

- **Parsing**
  - Group only when both group_by and aggregates are truthy; preserve first group occurrence order.

### `aggregates`

- **Output**
  - Aggregate expressions.

- **Source**
  - Call argument.

- **IR**
  - `list[AggregateSpec]`

- **Parsing**
  - See [aggregates](aggregate.md). Alone, without group_by, does not aggregate.

### `order_by`

- **Output**
  - Ordered sort specifications.

- **Source**
  - Call argument.

- **IR**
  - `list[OrderSpec]`

- **Parsing**
  - Stable multi-key sort; see [ordering](order.md).

### `limit`

- **Output**
  - Maximum result rows.

- **Source**
  - Call argument.

- **IR**
  - `int | None`

- **Parsing**
  - Slice only if truthy and >0; zero/negative does not limit.

### `text`

- **Output**
  - Legacy table text.

- **Source**
  - Query result records.

- **IR**
  - `ParseResult.text`

- **Parsing**
  - `<table>`, `<tr>`, `<th>label`, `<td>value` with implicit boundaries; no DTX guarantee. Empty → `<table>
  - `. Label/value text uses html.escape. syntax_version=legacy-markup/0, media_type=text/plain.


## Source references

- [query_data](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/query.py#L42)
- [_resolve_query_source](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/query.py#L95)
- [_coerce_cell_value](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/query.py#L315)
- [_render_query_result](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/query.py#L448)
