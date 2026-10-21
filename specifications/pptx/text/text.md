# Text bodies

[PPTX](../README.md) / Text bodies

A text shape retains its DrawingML paragraph boundaries and inline reading content.

## Processing

An `a:fld` uses its saved direct `a:t` and `a:rPr` through the ordinary run
reader, including inherited formatting and hyperlinks. Fields are not evaluated
or renumbered; a missing cached text does not produce a guessed value. Unknown
paragraph children emit `UNSUPPORTED_PARAGRAPH_CHILD`; pPr/endParaRPr are skipped.
Pending breaks/tabs are flushed before runs, fields and equations and at paragraph end.

List labels and placeholder roles are reading content in every density.
Resolve paragraph defaults through master, layout and shape declarations without
enabling character-color/geometry work in plain or structural plans. A replacement
bullet/number style removes the previous list kind; explicit `buNone` cancels
inherited numbering instead of letting the master label reappear.

## Fields

### `text`

- **Output**
  - A single retained paragraph uses `p`/`title`. Multiple retained paragraphs use
    one `textbox` with the object's `shape-id`, group and navigation attributes;
    each source paragraph is a child `p`. A title textbox has `role="title"`.
  - Plain output separates paragraphs with LF and uses two spaces per list level
    (clamped to 0..8); soft-break continuations retain that indentation.

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
  - Child paragraphs inside a multi-paragraph `textbox`, with nonzero `level`.
    A single paragraph uses the same level rule on its existing `p`/`title`.
    Visible labels preserve numbering; source list attributes remain internal.

- **OOXML**
  - a:p.

- **IR**
  - `list[Paragraph]`

- **Parsing**
  - Retain every nonempty parsed paragraph with its own text and runs, including
    non-list paragraphs. Runs preserve links, formatting and equations across
    paragraph boundaries. A list declaration without visible paragraph content
    does not create a visible marker or consume an automatic number.
  - Adjacent runs with the same effective public formatting and hyperlink share
    their XML wrappers. Equations remain separate. This changes neither text nor
    effective emphasis/color/link semantics and does not mutate the retained IR.

### `equation`

- **Output**
  - `<equation notation="latex">...</equation>`.

- **OOXML**
  - Direct paragraph oMath/oMathPara.

- **IR**
  - `Run.equation: str`

- **Parsing**
  - Use [OMML conversion](../../common/equation.md); also store LaTeX as text for plain output. Empty conversion yields no run.
