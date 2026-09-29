# Query ordering

[XLSX](../README.md) / Query ordering

Sort runs after selection, against the resulting column catalog.

## Fields

### `column`

- **Output**
  - Sort key.

- **Source**
  - Call dictionary.

- **IR**
  - `str`

- **Parsing**
  - Resolve when supplied; omitted uses empty key.

### `direction`

- **Output**
  - Sort direction.

- **Source**
  - Call dictionary.

- **IR**
  - `str`

- **Parsing**
  - asc/desc only when supplied; default ascending. Ascending numbers precede strings; descending reverses both category and value. Sort keys are stable in request priority order.


## Source references

- [_resolve_order_specs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/query.py#L231)
- [_apply_order_by](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/_query_operations.py#L121)
- [_order_key](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/_query_operations.py#L133)
