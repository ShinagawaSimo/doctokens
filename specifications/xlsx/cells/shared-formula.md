# Shared formulas

[XLSX](../README.md) / Shared formulas

A shared group is resolved within a worksheet.

## Synopsis

```python
def _offset_one_ref(
    col_abs: bool,
    row_abs: bool,
    col_str: str,
    row_str: str,
    dc: int,
    dr: int,
) -> str:
    """Apply offset to a single cell reference, respecting absolute anchors."""
    c = _col_from_str(col_str)
    r = int(row_str)
    if not col_abs:
        c += dc
    if not row_abs:
        r += dr
    col_frag = col_letter(c)
    row_frag = str(r)
    return f"{'$' if col_abs else ''}{col_frag}{'$' if row_abs else ''}{row_frag}"
```

## Processing

The implementation recognizes uppercase 1–3 letter columns and decimal row digits. It rejects matches embedded after an alphanumeric character and matches resembling function calls. Relative offsets are not clamped to worksheet bounds.

## Fields

### `si`

- **Output**
  - Internal shared-group key.

- **OOXML**
  - s:f[@t="shared"]/@si.

- **IR**
  - `Cell.si: str`

- **Parsing**
  - Retain any present attribute, including empty; group by exact string.

### `shared_ref`

- **Output**
  - Internal master marker.

- **OOXML**
  - s:f[@t="shared"]/@ref.

- **IR**
  - `Cell.shared_ref: str`

- **Parsing**
  - Keep nonempty ref; first cell in group with truthy shared_ref becomes master. No master → group unchanged, no warning.

### `formula`

- **Output**
  - Per-cell formula attribute.

- **OOXML**
  - Master formula and coordinate offsets.

- **IR**
  - `Cell.formula: str`

- **Parsing**
  - Empty master → all slaves get empty string. Otherwise offset matched relative A1 components by slave-master delta; $ anchors remain fixed; double-quoted literals remain unchanged; matched sheet-qualified references remain unchanged. This is regex-based translation, not a full Excel formula grammar.


## Source references

- [expand_shared_formula_groups](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/formulas.py#L62)
- [_offset_formula](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/formulas.py#L119)
