# Query conditions

[XLSX](../README.md) / Query conditions

Predicates are combined with logical AND.

## Fields

### `column`

- **Output**
  - Predicate field.

- **Source**
  - Call dictionary.

- **IR**
  - `WhereCondition.column: str`

- **Parsing**
  - Required; resolve using [columns](column.md); missing → ValueError.

### `op`

- **Output**
  - Comparison operation.

- **Source**
  - Call dictionary.

- **IR**
  - `str = "eq"`

- **Parsing**
  - eq → str(actual)==str(expected); contains → case-insensitive substring; gt/lt → actual must be int/float, expected float(str(value)). Unknown operator → ValueError.

### `value`

- **Output**
  - Expected operand.

- **Source**
  - Call dictionary.

- **IR**
  - `object`

- **Parsing**
  - Default None; numeric conversion failure makes gt/lt false. Missing actual value is None.


## Source references

- [_resolve_where_conditions](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/query.py#L190)
- [_matches_condition](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/_query_operations.py#L23)
