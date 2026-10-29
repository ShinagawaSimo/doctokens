# Cell styles

[XLSX](../README.md) / Cell styles

Semantic styles use the effective cell-XF and its font/fill references. Cell XF selection is defined in [cells](../cells/cell.md#style). Font/fill IDs inherit a valid cellStyleXf parent when the corresponding apply flag is false or the direct ID is absent, matching effective number-format inheritance.

Differential-style summaries retain explicitly disabled font properties as `bold=false`, `italic=false`, or `underline=false`. A false override in a saved conditional rule is not equivalent to an absent property and must not be summarized as an enabled style.

## Fields

### `bold`

- **Output**
  - cell/style-range @bold=true.

- **OOXML**
  - Referenced font/b.

- **IR**
  - `FontInfo.bold`

- **Parsing**
  - Absent: false. Present with no val: true. Explicit 0/false/off: false. Source values are case-normalized for this on/off interpretation.

### `italic`

- **Output**
  - @italic=true.

- **OOXML**
  - font/i.

- **IR**
  - `FontInfo.italic`

- **Parsing**
  - Same on/off interpretation as bold.

### `underline`

- **Output**
  - @underline=true.

- **OOXML**
  - font/u.

- **IR**
  - `FontInfo.underline`

- **Parsing**
  - No val means single; 0/false/off/none disable underline. Other underline styles collapse to one reading underline.

### `color`

- **Output**
  - @color.

- **OOXML**
  - font/color.

- **IR**
  - `FontInfo.color`

- **Parsing**
  - Resolve [color](color.md); omit #000000 in ordinary cell style_attrs.

### `fill`

- **Output**
  - @fill.

- **OOXML**
  - fill/patternFill/fgColor.

- **IR**
  - `FillInfo.fill`

- **Parsing**
  - Resolve color regardless of pattern type; background/gradient fills are not represented.

### `locked`

- **Output**
  - cell/@locked=false.

- **OOXML**
  - xf/protection/@locked.

- **IR**
  - Cell-format bool.

- **Parsing**
  - Default true; exact "0" → false. Output is not gated by sheet_protection.

### `formulaHidden`

- **Output**
  - cell/@formula-hidden=true.

- **OOXML**
  - xf/protection/@hidden.

- **IR**
  - Cell-format bool.

- **Parsing**
  - Default false; exact "1" → true. Formula text remains available; parser does not enforce protection.
