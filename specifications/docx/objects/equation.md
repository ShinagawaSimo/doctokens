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
  - `omath_to_latex(node)`; XML escaping is applied after conversion. See [OMML](../../common/equation.md).

### `notation`

- **Output**
  - `notation="latex"`.

- **OOXML**
  - Serializer constant.

- **IR**
  - No separate member.

- **Parsing**
  - Always latex; conversion does not execute a TeX engine.


## Source references

- [equation_object](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/objects.py#L82)
- [_append_inline_object](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L164)
