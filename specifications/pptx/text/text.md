# Text bodies

[PPTX](../README.md) / Text bodies

A text shape flattens its DrawingML paragraphs into one readable text body.

## Processing

Fields recurse into their children; they are not evaluated. A direct a:t under a:fld is not handled as a run and reports UNSUPPORTED_PARAGRAPH_CHILD. Unknown paragraph children emit the same warning; pPr/endParaRPr are skipped. Pending breaks/tabs are flushed before ordinary runs and fields and at paragraph end; equation insertion does not flush them.

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


## Source references

- [shape_runs](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/runs.py#L52)
- [paragraph_runs](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/runs.py#L106)
- [_append_shape_text](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L151)
