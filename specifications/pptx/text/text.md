# Text bodies

[PPTX](../README.md) / Text bodies

A text shape flattens its DrawingML paragraphs into one readable text body.

## Processing

An `a:fld` uses its saved direct `a:t` and `a:rPr` through the ordinary run
reader, including inherited formatting and hyperlinks. Fields are not evaluated
or renumbered; a missing cached text does not produce a guessed value. Unknown
paragraph children emit `UNSUPPORTED_PARAGRAPH_CHILD`; pPr/endParaRPr are skipped.
Pending breaks/tabs are flushed before runs, fields and equations and at paragraph end.

## Fields

### `text`

- **Output**
  - Text inside p/title; plain text.

- **OOXML**
  - p:txBody/a:p/a:r/a:t, breaks, tabs, fields, equations.

- **IR**
  - `ShapeBlock.text: str`; `Run.text: str`

- **Parsing**
  - Copy first direct a:t of each run; add LF for br and TAB for tab. Join retained paragraph runs with synthetic LF; include visible list prefix. Empty result becomes a descriptive shape.

### `runs`

- **Output**
  - DTX inline sequence.

- **OOXML**
  - DrawingML paragraphs.

- **IR**
  - `list[Run]`

- **Parsing**
  - Retain on ShapeBlock only if some run has a key other than text. Serialize in order; fallback to shape text. Literal LF/TAB remain character data in PPTX DTX.

### `paragraphs`

- **Output**
  - Internal list metadata.

- **OOXML**
  - a:p.

- **IR**
  - `list[Paragraph]`

- **Parsing**
  - Retain on shape only if at least one paragraph has bullet/numberType. No separate paragraph metadata elements in DTX.

### `equation`

- **Output**
  - `<equation notation="latex">...</equation>`.

- **OOXML**
  - Direct paragraph oMath/oMathPara.

- **IR**
  - `Run.equation: str`

- **Parsing**
  - Use [OMML conversion](../../common/equation.md); also store LaTeX as text for plain output. Empty conversion yields no run.
