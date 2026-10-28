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
  - `w:fldSimple/@w:instr`; complex `w:fldChar` + `w:instrText`, or selected deletion `w:delInstrText`.

- **IR**
  - `Run.field.kind: "citation" | "reference"`

- **Parsing**
  - Recognize REF/PAGEREF/NOTEREF/HYPERLINK/CITATION case-insensitively. Use Word field tokens, not shell syntax: double quotes group arguments, `\"` represents a literal quote, and `\\` represents a literal backslash. Apostrophes are ordinary characters. Switches can adjoin quoted arguments without whitespace.
  - Consume switch arguments before selecting the single positional argument. General `\*`, `\#`, and `\@` consume one value. HYPERLINK `\l/\o/\t`, REF `\d`, and CITATION `\l/\m/\p/\s/\v/\f` consume one value. Recognized flags are HYPERLINK `\m/\n`, REF `\f/\h/\n/\p/\r/\t/\w`, PAGEREF `\h/\p`, NOTEREF `\f/\h/\p`, and CITATION `\n/\t/\y`.

- **Absence and defaults**
  - Unknown instructions leave result text unchanged.

- **Diagnostics**
  - Recognized fields with unclosed quotes, incomplete escapes, missing switch arguments, unsupported switches, or ambiguous positional arguments report `INVALID_FIELD_INSTRUCTION` at the owning part/block. Keep saved result text and add no guessed link/citation metadata. There is no whitespace-tokenizer fallback.

### `key`

- **Output**
  - Semantic `<cite key="...">result</cite>`.

- **OOXML**
  - The single positional argument of CITATION, after consuming switch arguments.

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
  - REF/PAGEREF/NOTEREF use their positional target. HYPERLINK uses its positional address as href and `\l` argument as anchor; either can appear alone. `\o` tooltip and `\t` target-window values are never addresses.
  - Example: `HYPERLINK \l "Target"` renders `<a anchor="Target">result</a>`; `HYPERLINK "https://example.test" \l "Target"` emits both attributes and refers to the remote document fragment.

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
