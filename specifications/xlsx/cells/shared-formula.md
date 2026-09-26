# Shared formulas

[XLSX](../README.md) / [Cells](cell.md) / Shared formulas

A shared formula group is scoped to one worksheet. In structural and semantic output, a selected dependent cell can use a master declaration outside the selected range. Only selected cells enter the grid; an outside master contributes its reference, range, shared index, and formula text to expansion.

## Fields

### `si`

- **Output**
  - No DTX attribute; identifies a shared group during parsing.
- **OOXML**
  - `s:c/s:f[@t="shared"]/@si`.
- **IR**
  - `Cell.si: str`; `SharedFormulaMaster.si: str`.
- **Parsing**
  - Present values, including `""`, are grouped by exact string within the worksheet. A shared formula without `@si` does not enter a group.
  - Up to two distinct master declarations are retained per group; a second distinct declaration establishes a conflict. Identical declarations are deduplicated.

### `shared_ref`

- **Output**
  - No DTX attribute; constrains which cells can receive an expanded formula.
- **OOXML**
  - `s:c/s:f[@t="shared"]/@ref` on a master declaration.
- **IR**
  - `Cell.shared_ref: str`; `SharedFormulaMaster.shared_ref: str`.
- **Parsing**
  - A present `@ref` makes the cell a master candidate, even when the value is empty. The range accepts one A1 cell or `A1:B2`, with one to three uppercase ASCII letters per column, positive rows, ascending bounds, and Excel limits of 16,384 columns and 1,048,576 rows.
  - The master's coordinate and every selected group member must be inside the range. A selected group containing no dependent cell needs no expansion.
- **Diagnostics**
  - `SHARED_FORMULA_INVALID` if a selected dependent has conflicting masters, an invalid range, or a member outside that range. The cached cell value and any source formula remain unchanged.

### `formula`

- **Output**
  - `cell/@formula` in structural and semantic DTX. Plain output uses the saved display value and does not collect shared-formula dependencies.
- **OOXML**
  - Master `s:f` text; dependent `s:f[@t="shared"]` may have no text. Saved `s:v` supplies the independent cached value.
- **IR**
  - `SharedFormulaMaster.formula: str`; `Cell.formula: str`.
- **Parsing**
  - For a dependent at `(column, row)`, subtract the master's coordinate and apply that offset to relative A1 components in the master formula. `$`-anchored components are unchanged. Double-quoted literals and matched sheet-qualified references are unchanged.
  - Matching recognizes one to three uppercase column letters and decimal row digits; it excludes references embedded after an alphanumeric character and matches resembling function calls. Translation is lexical and does not evaluate formulas, clamp out-of-bounds results, or parse the full Excel formula language.
  - The source formula and cached value on a selected master are retained. A dependent receives no inferred formula when expansion fails.
- **Diagnostics**
  - `SHARED_FORMULA_UNRESOLVED` when a selected dependent has no master or the sole valid master has empty formula text.
  - `SHARED_FORMULA_INVALID` takes precedence for a conflicting or invalid declaration. One warning is emitted per affected worksheet group and reason; its locator is `worksheet-part!selected-dependent-reference`.

## Source references

- [WorksheetScanner.parse](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py)
- [expand_selected_shared_formulas](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/formulas.py)
- [_offset_formula](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/formulas.py)
