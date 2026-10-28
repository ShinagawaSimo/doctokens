# Equations

[DOCX](../README.md) / Equations

OMML is converted by the shared expression converter.

## Fields

### `text`

- **Output**
  - `<equation notation="latex">...</equation>`.

- **OOXML**
  - `m:oMath`, `m:oMathPara`.

- **IR**
  - `InlineObject.text: str`

- **Parsing**
  - `convert_math(node, revision_mode=...)` in [equations.py](../../../packages/doctokens_word/src/doctokens_word/docx/parsing/modules/body/equations.py); XML escaping is applied after conversion. See [OMML](../../common/equation.md).
  - Pass the containing document's revision view. A formula with no retained text after filtering does not create an empty visible formula placeholder.
  - Semantic review keeps nested insertion/deletion fragments as mixed XML content inside `equation`, including author/date when saved. Concatenate `itertext()` to obtain the complete LaTeX. Structural/plain keep the selected view's formula text without these inline review wrappers.
  - Whole inserted/deleted formulas retain the enclosing run's semantic review wrapper. Deleted formula objects keep their mathematical structure rather than becoming a concatenation of deleted letters.
  - Conversion degradation and unknown symbol-encoding diagnostics enter the ordinary parse report with their owning part/block.

### `notation`

- **Output**
  - `notation="latex"`.

- **OOXML**
  - Serializer constant.

- **IR**
  - No separate member.

- **Parsing**
  - Always latex; conversion does not execute a TeX engine.
