# Spreadsheet colors

[XLSX](../README.md) / Spreadsheet colors

Cell fonts and fills use the workbook theme when necessary.

## Fields

### `rgb`

- **Output**
  - #RRGGBB-style output string.

- **OOXML**
  - color/@rgb.

- **IR**
  - Resolved string.

- **Parsing**
  - Require six or eight hexadecimal digits, remove the optional alpha byte
    and normalize to uppercase RGB. Automatic color is not a guessed RGB.

### `theme`

- **Output**
  - Resolved theme color.

- **OOXML**
  - color/@theme.

- **IR**
  - Integer theme index.

- **Parsing**
  - Slots 0..11 are lt1, dk1, lt2, dk2, accent1..6, hlink, folHlink.
    Read the workbook's theme relationship target, otherwise the conventional
    theme1.xml path. Preserve the existing Office-default fallback for an
    absent theme. Cell fonts, fills, differential styles, shared strings and
    inline rich runs use the same per-workbook SpreadsheetColors context.

### `tint`

- **Output**
  - Adjusted theme color.

- **OOXML**
  - color/@tint.

- **IR**
  - float.

- **Parsing**
  - Apply to a resolved RGB/theme/indexed color in HLS space. Negative tint
    scales luminance by 1+tint; positive tint uses L*(1-tint)+tint.
    Convert back to RGB and round channels to byte values. Require a finite
    tint within -1..1; invalid tint preserves the base property.

### `indexed`

- **Output**
  - Resolved RGB from the workbook's indexed palette or the default palette.

- **OOXML**
  - color/@indexed.

- **IR**
  - Per-workbook SpreadsheetColors.indexed.

- **Parsing**
  - Read styles/colors/indexedColors/rgbColor entries as indexed overrides;
    omitted positions retain the standard 64-entry palette. Entries 0..63
    resolve directly, for example indexed=10 is FF0000. Indices 64/65 are
    application/system colors and are not guessed; invalid indices cannot
    invoke Python negative indexing.
