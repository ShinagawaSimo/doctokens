# Query aggregates

[XLSX](../README.md) / Query aggregates

Aggregates run only inside a requested grouping operation.

## Fields

### `op`

- **Output**
  - Aggregate operation.

- **Source**
  - Call dictionary.

- **IR**
  - `str = "sum"`

- **Parsing**
  - Accepted operators: `sum`, `count`, `avg`, `min`, `max`. An unknown operator raises `ValueError`.
  - `count` counts rows, including rows whose selected value is absent or non-numeric. Other operations ignore non-numeric values.
  - `avg` rounds to four decimal places and returns `0` when no numeric values are present.

### `column`

- **Output**
  - Input field.

- **Source**
  - Call dictionary.

- **IR**
  - `str`

- **Parsing**
  - Resolve when supplied; omitted uses empty key. sum/min/max with no numeric input leave output key absent.

### `as`

- **Output**
  - Output field label/key.

- **Source**
  - Call dictionary.

- **IR**
  - `str`

- **Parsing**
  - Truthy alias wins; otherwise op_column. Colliding aliases can overwrite results.


## Source references

- [_resolve_aggregates](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/query.py#L211)
- [_update_group](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/_query_operations.py#L60)
- [_finalize_averages](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/_query_operations.py#L95)
