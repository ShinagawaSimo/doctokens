# Fields

[DOCX](../README.md) / Fields

Saved field results are read; fields are not evaluated.

## Processing

Complex-field stack is reset for each paragraph. `begin` pushes; `separate` records the current run position; `end` applies the accumulated instruction to subsequent result runs. Simple fields parse their child runs first.

## Fields

### `kind`

- **Output**
  - Semantic cite or reference link.

- **OOXML**
  - `w:fldSimple/@w:instr`; complex `w:fldChar` + `w:instrText`.

- **IR**
  - `Run.field.kind: "citation" | "reference"`

- **Parsing**
  - Tokenize with `shlex.split`, fallback whitespace split on ValueError. Match uppercase instruction keyword. Recognize REF/PAGEREF/NOTEREF/HYPERLINK/CITATION.

- **Absence and defaults**
  - Unknown instructions leave result text unchanged.

### `key`

- **Output**
  - Semantic `<cite key="...">result</cite>`.

- **OOXML**
  - First non-switch payload of CITATION.

- **IR**
  - `Run.field.key: str`

- **Parsing**
  - Attach to every parsed result run; no bibliography execution.

### `anchor`

- **Output**
  - DTX link anchor.

- **OOXML**
  - Reference payload or HYPERLINK local switch.

- **IR**
  - `Run.field.anchor: str`; `Run.link`

- **Parsing**
  - REF/PAGEREF/NOTEREF use first non-switch token. HYPERLINK handling follows the source parser below.

- **Absence and defaults**
  - No target: no semantic link.

### `instruction`

- **Output**
  - `<field instruction="..."/>` only if an IR `fieldInstruction` object exists.

- **OOXML**
  - Field instruction text.

- **IR**
  - `InlineObject.instruction: str`

- **Parsing**
  - Current ordinary field parser collects instructions to annotate saved result runs; unknown instructions are not automatically converted to this object.

- **Absence and defaults**
  - Absent from main output unless the object was produced.


## Source references

- [RunParser.handle_field_character](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/runs.py#L200)
- [RunParser.apply_field_instruction](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/runs.py#L224)
- [_append_inline_object](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L167)
