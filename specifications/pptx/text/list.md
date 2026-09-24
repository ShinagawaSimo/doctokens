# Bullets and numbering

[PPTX](../README.md) / Bullets and numbering

List labels are inserted into the text and remain visible in every density.

## Fields

### `text`

- **Output**
  - Visible list prefix + paragraph text.

- **OOXML**
  - List declaration and paragraph content.

- **IR**
  - `Paragraph.text: str`

- **Parsing**
  - Number/bullet followed by one space; source text follows.

### `level`

- **Output**
  - Internal list nesting level.

- **OOXML**
  - a:pPr/@lvl.

- **IR**
  - `Paragraph.level: int`

- **Parsing**
  - int(value), default 0 on missing/malformed; inherited style lookup uses level then level 0.

### `bullet`

- **Output**
  - Visible bullet character.

- **OOXML**
  - a:buChar/@char or inherited bullet.

- **IR**
  - `Paragraph.bullet: str`

- **Parsing**
  - Direct buNone suppresses; direct buChar wins over auto numbering, default bullet •. Inherited bullet applies only with no direct auto.

### `numberType`

- **Output**
  - Visible formatted counter.

- **OOXML**
  - a:buAutoNum/@type or inherited numberType.

- **IR**
  - `Paragraph.numberType: str`

- **Parsing**
  - Default arabicPeriod. Counter key `(number_type, level)` scoped to txBody; format using format_drawingml_autonumber.

### `startAt`

- **Output**
  - Initial counter value.

- **OOXML**
  - a:buAutoNum/@startAt or inherited value.

- **IR**
  - `Paragraph.startAt: int`

- **Parsing**
  - First use of key → parsed start; later uses increment, even if a new startAt appears. Default/failure → 1 (prefix can use inherited start). No deeper-level reset rule.


## Source references

- [_list_prefix](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L973)
- [_list_metadata](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L1002)
- [format_drawingml_autonumber](../../../packages/ooxml_llm_core/src/ooxml_llm_core/text_numbering.py#L43)
