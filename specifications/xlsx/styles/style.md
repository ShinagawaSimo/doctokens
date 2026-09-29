# Cell styles

[XLSX](../README.md) / Cell styles

Semantic styles use cell-XF font/fill references.

## Fields

### `bold`

- **Output**
  - cell/style-range @bold=true.

- **OOXML**
  - Referenced font/b.

- **IR**
  - `FontInfo.bold`

- **Parsing**
  - Presence=true; val is not interpreted.

### `italic`

- **Output**
  - @italic=true.

- **OOXML**
  - font/i.

- **IR**
  - `FontInfo.italic`

- **Parsing**
  - Presence=true.

### `underline`

- **Output**
  - @underline=true.

- **OOXML**
  - font/u.

- **IR**
  - `FontInfo.underline`

- **Parsing**
  - Presence=true.

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


## Source references

- [parse_styles](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/parser.py#L17)
- [font_info](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/records.py#L79)
- [fill_info](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/records.py#L96)
- [_cell_attrs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L156)
