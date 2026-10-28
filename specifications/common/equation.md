# OMML expressions

[COMMON](README.md) / OMML expressions

OMML nodes produce LaTeX text through recursive conversion. The result is a reading representation; layout and font fidelity are not reconstructed.

## Processing

`omath_to_latex(root)` converts its children. Dispatch uses the element local name. Unrecognized elements use escaped descendant math text; they do not emit a diagnostic.

## Fields

### `r`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:r`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_r](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_r(elem: ET.Element) -> str:
      parts: list[str] = []
      for child in elem:
          if local_name(child.tag) == "t":
              text = child.text or ""
              parts.append(_escape_latex(text))
      return "".join(parts)
  ```

### `t`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:t`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_t](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_t(elem: ET.Element) -> str:
      return _escape_latex(elem.text or "")
  ```

### `f`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:f`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_f](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_f(elem: ET.Element) -> str:
      num = _child_convert(elem, "num")
      den = _child_convert(elem, "den")
      return rf"\frac{{{num}}}{{{den}}}"
  ```

### `rad`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:rad`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_rad](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_rad(elem: ET.Element) -> str:
      deg = _child_convert(elem, "deg")
      e_val = _child_convert(elem, "e")
      if deg:
          return rf"\sqrt[{deg}]{{{e_val}}}"
      return rf"\sqrt{{{e_val}}}"
  ```

### `sSub`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sSub`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_ssub](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_ssub(elem: ET.Element) -> str:
      e_val = _child_convert(elem, "e")
      sub = _child_convert(elem, "sub")
      e_out = _wrap_group(e_val)
      return f"{e_out}_{{{sub}}}"
  ```

### `sSup`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sSup`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_ssup](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_ssup(elem: ET.Element) -> str:
      e_val = _child_convert(elem, "e")
      sup = _child_convert(elem, "sup")
      e_out = _wrap_group(e_val)
      return f"{e_out}^{{{sup}}}"
  ```

### `sSubSup`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sSubSup`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_ssubsup](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_ssubsup(elem: ET.Element) -> str:
      e_val = _child_convert(elem, "e")
      sub = _child_convert(elem, "sub")
      sup = _child_convert(elem, "sup")
      e_out = _wrap_group(e_val)
      result = e_out
      if sub:
          result += f"_{{{sub}}}"
      if sup:
          result += f"^{{{sup}}}"
      return result
  ```

### `sPre`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sPre`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_spre](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_spre(elem: ET.Element) -> str:
      e_val = _child_convert(elem, "e")
      sub = _child_convert(elem, "sub")
      sup = _child_convert(elem, "sup")
      parts: list[str] = []
      if sub:
          parts.append(f"_{{{sub}}}")
      if sup:
          parts.append(f"^{{{sup}}}")
      parts.append(_wrap_group(e_val))
      return "{}" + "".join(parts)
  ```

### `nary`

- **Output**
  - LaTeX operator, visible lower/upper limits, then the grouped base.
- **OOXML**
  - m:nary/m:naryPr; direct m:sub, m:sup, m:e.
- **IR**
  - Recursive string result.
- **Parsing**
  - [nary](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/operators.py).
  - Read chr from naryPr/chr/@m:val. Missing chr means integral U+222B, not summation. A present chr without val, or with an empty val, means no operator.
  - Map known integral/product/sum/set operators through _NARY_OPERATOR_MAP. Preserve any other explicit character as escaped text rather than inventing a sum.
  - Convert visible sub/sup as _{...}/^{...}. Missing subHide/supHide means false; a present flag without val means true; 0/false/off means false.
  - Omit hidden limits even when their saved arguments contain text. An empty operator with visible limits uses an empty TeX base {}.
  - Example: chr="∏", sub="k=1", sup="n", e="A" → \prod_{k=1}^{n} {A}.

### `acc`

- **Output**
  - A mapped LaTeX accent over the converted base.
- **OOXML**
  - m:acc/m:accPr/m:chr/@m:val; m:acc/m:e.
- **IR**
  - Recursive string result.
- **Parsing**
  - [accent](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/operators.py).
  - Missing chr defaults to combining circumflex U+0302. A present empty chr, including missing val, leaves the base undecorated.
  - Known characters map through _ACCENT_MAP, including vector, dot, double dot, tilde and hat. Preserve an unknown explicit character with \overset{character}{base}.
  - Example: chr="⃗", e="v" → \vec{v}.

### `bar`

- **Output**
  - \overline{base} or \underline{base}.
- **OOXML**
  - m:bar/m:barPr/m:pos/@m:val; m:bar/m:e.
- **IR**
  - Recursive string result.
- **Parsing**
  - [bar](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/operators.py).
  - Explicit top selects overline; bot selects underline. An omitted pos or omitted val defaults to bot, as in ISO/IEC 29500-1:2016 §22.1.2.84 and Office.
  - Example: pos="bot", e="q" → \underline{q}.

### `func`

- **Output**
  - LaTeX function name, its saved limits/scripts and its grouped argument.
- **OOXML**
  - m:func/m:fName and m:func/m:e.
- **IR**
  - Recursive string result.
- **Parsing**
  - [_handle_func](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py).
  - Map simple names through _FUNC_MAP; escape other names inside \operatorname{...}.
  - Preserve limLow/limUpp and sSub/sSup/sSubSup within fName, recursively converting the function base and limit arguments. Do not flatten limit text into the name.
  - The previously accepted direct m:lim also adds a lower limit when present.
  - Example: fName/limLow with e="lim", lim="x→0", outer e="f" → \lim_{x→0}{f}.

### `groupChr`

- **Output**
  - A brace/arrow command or an explicit character above/below the base.
- **OOXML**
  - m:groupChr/m:groupChrPr/{m:chr,m:pos}/@m:val; direct m:e.
- **IR**
  - Recursive string result.
- **Parsing**
  - [group_character](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/operators.py).
  - Missing chr defaults to bottom curly bracket U+23DF; present empty chr leaves the base undecorated. Missing pos or val defaults to bot.
  - Upper U+23DE at top maps to \overbrace; lower U+23DF at bot maps to \underbrace.
  - Left/right/bidirectional arrows use the corresponding over/under arrow commands. Other explicit character/position pairs use \overset or \underset and preserve escaped character text.
  - Vertical baseline justification and exact stretching are not reconstructed.

### `d`

- **Output**
  - Converted arguments in their saved delimiters, joined by the saved separator.
- **OOXML**
  - m:d/m:dPr/{m:begChr,m:sepChr,m:endChr}/@m:val; every direct m:e.
- **IR**
  - Recursive string result.
- **Parsing**
  - [delimiter](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/operators.py).
  - Omitted begChr/endChr default to ( and ); omitted sepChr defaults to |. U+2502 is normalized to the same separator.
  - A present character element with no val or an empty val means no character. It does not restore the default. Empty outer delimiters use TeX \left. or \right.; an empty separator concatenates arguments.
  - Convert all e children in order. Known delimiters use _DELIM_MAP and \left/\right. Other explicit characters use \mathopen/\mathclose; do not generate an invalid TeX delimiter pair.
  - Example: square brackets, separator ;, e="x" and e="y" → \left[ x;y \right].
  - Example: default properties and the same arguments → \left( x|y \right).

### `m`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:m`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_m](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_m(elem: ET.Element) -> str:
      rows: list[str] = []
      for mr in child_elements(elem, "m", "mr"):
          cells = [_convert_node(cell) for cell in mr if local_name(cell.tag) == "e"]
          rows.append(" & ".join(cells))
      body = r" \\ ".join(rows)
      return rf"\begin{{matrix}} {body} \end{{matrix}}"
  ```

### `eqArr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:eqArr`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_eqarr](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_eqarr(elem: ET.Element) -> str:
      rows = [_convert_node(child) for child in elem if local_name(child.tag) == "e"]
      body = r" \\ ".join(rows)
      return rf"\begin{{aligned}} {body} \end{{aligned}}"
  ```

### `limLow`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:limLow`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_limlow](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_limlow(elem: ET.Element) -> str:
      e_val = _child_convert(elem, "e")
      lim = _child_convert(elem, "lim")
      return f"{{{e_val}}}_{{{lim}}}"
  ```

### `limUpp`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:limUpp`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_limupp](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_limupp(elem: ET.Element) -> str:
      e_val = _child_convert(elem, "e")
      lim = _child_convert(elem, "lim")
      return f"{{{e_val}}}^{{{lim}}}"
  ```

### `phant`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:phant`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_phant](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_phant(elem: ET.Element) -> str:
      e_val = _child_convert(elem, "e")
      return rf"\phantom{{{e_val}}}"
  ```

### `borderBox`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:borderBox`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_borderbox](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_borderbox(elem: ET.Element) -> str:
      e_val = _child_convert(elem, "e")
      return rf"\boxed{{{e_val}}}"
  ```

### `box`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:box`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_box](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _handle_box(elem: ET.Element) -> str:
      return _convert_children(elem)
  ```

### `oMath`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:oMath`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_convert_children](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _convert_children(elem: ET.Element) -> str:
      parts: list[str] = []
      for child in elem:
          latex = _convert_node(child)
          if latex:
              parts.append(latex)
      return "".join(parts)
  ```

### `oMathPara`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:oMathPara`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_convert_children](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _convert_children(elem: ET.Element) -> str:
      parts: list[str] = []
      for child in elem:
          latex = _convert_node(child)
          if latex:
              parts.append(latex)
      return "".join(parts)
  ```

### `e`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:e`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_convert_children](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _convert_children(elem: ET.Element) -> str:
      parts: list[str] = []
      for child in elem:
          latex = _convert_node(child)
          if latex:
              parts.append(latex)
      return "".join(parts)
  ```

### `num`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:num`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_convert_children](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _convert_children(elem: ET.Element) -> str:
      parts: list[str] = []
      for child in elem:
          latex = _convert_node(child)
          if latex:
              parts.append(latex)
      return "".join(parts)
  ```

### `den`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:den`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_convert_children](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _convert_children(elem: ET.Element) -> str:
      parts: list[str] = []
      for child in elem:
          latex = _convert_node(child)
          if latex:
              parts.append(latex)
      return "".join(parts)
  ```

### `sub`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sub`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_convert_children](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _convert_children(elem: ET.Element) -> str:
      parts: list[str] = []
      for child in elem:
          latex = _convert_node(child)
          if latex:
              parts.append(latex)
      return "".join(parts)
  ```

### `sup`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sup`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_convert_children](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _convert_children(elem: ET.Element) -> str:
      parts: list[str] = []
      for child in elem:
          latex = _convert_node(child)
          if latex:
              parts.append(latex)
      return "".join(parts)
  ```

### `deg`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:deg`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_convert_children](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _convert_children(elem: ET.Element) -> str:
      parts: list[str] = []
      for child in elem:
          latex = _convert_node(child)
          if latex:
              parts.append(latex)
      return "".join(parts)
  ```

### `lim`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:lim`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_convert_children](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)

- **Conversion**

  ```python
  def _convert_children(elem: ET.Element) -> str:
      parts: list[str] = []
      for child in elem:
          latex = _convert_node(child)
          if latex:
              parts.append(latex)
      return "".join(parts)
  ```

### `fName`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:fName`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_function_name](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py), preserving nested limits and scripts.

### `chr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:chr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: e.get(qualified_name('m', 'val'), '')`

### `oMathParaPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:oMathParaPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `oMathPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:oMathPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `sSubPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sSubPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `sSupPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sSupPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `sSubSupPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sSubSupPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `sPrePr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sPrePr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `fPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:fPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `naryPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:naryPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `radPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:radPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `accPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:accPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `barPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:barPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `dPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:dPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `mPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:mPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `eqArrPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:eqArrPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `groupChrPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:groupChrPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `ctrlPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:ctrlPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `rPr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:rPr`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `sty`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:sty`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

### `jc`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:jc`

- **IR**
  - Recursive string result.

- **Parsing**
  - `lambda e: ''`

## Character conversion

- [_escape_latex](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/support.py)
- [_plain_text](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/support.py)
- [_wrap_group](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/support.py)
- [_property](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/operators.py)

Literal TeX special characters are escaped once per source character, including text from unknown-node fallback. Generated command braces are not re-escaped. For example, a literal backslash becomes `\textbackslash{}`.
