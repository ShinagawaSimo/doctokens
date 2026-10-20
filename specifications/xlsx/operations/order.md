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
