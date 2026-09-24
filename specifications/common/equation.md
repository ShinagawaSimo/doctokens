# OMML expressions

[COMMON](README.md) / OMML expressions

OMML nodes produce LaTeX text through recursive conversion. The result is a reading representation; layout and font fidelity are not reconstructed.

## Processing

`omath_to_latex(root)` converts its children. Dispatch uses the element local name. Unrecognized elements use descendant text; they do not emit a diagnostic.

## Fields

### `r`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:r`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_r](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L149)

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
  - [_handle_t](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L159)

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
  - [_handle_f](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L167)

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
  - [_handle_rad](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L177)

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
  - [_handle_ssub](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L189)

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
  - [_handle_ssup](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L197)

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
  - [_handle_ssubsup](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L205)

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
  - [_handle_spre](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L219)

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
      return "".join(parts)
  ```

### `nary`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:nary`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_nary](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L236)

- **Conversion**

  ```python
  def _handle_nary(elem: ET.Element) -> str:
      chr_val = _child_attr(elem, "chr", "val")
      op = _NARY_OPERATOR_MAP.get(chr_val or "", r"\sum")
  
      sub = _child_convert(elem, "sub")
      sup = _child_convert(elem, "sup")
      e_val = _child_convert(elem, "e")
  
      limits = ""
      if sub:
          limits += f"_{{{sub}}}"
      if sup:
          limits += f"^{{{sup}}}"
  
      return f"{op}{limits} {{{e_val}}}"
  ```

### `acc`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:acc`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_acc](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L259)

- **Conversion**

  ```python
  def _handle_acc(elem: ET.Element) -> str:
      chr_val = _child_attr(elem, "chr", "val")
      cmd = _ACCENT_MAP.get(chr_val or "", r"\hat")
      e_val = _child_convert(elem, "e")
      return f"{cmd}{{{e_val}}}"
  ```

### `bar`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:bar`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_bar](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L270)

- **Conversion**

  ```python
  def _handle_bar(elem: ET.Element) -> str:
      pos = _child_attr(elem, "pr", "pos") or "top"
      e_val = _child_convert(elem, "e")
      if pos == "bot":
          return rf"\underline{{{e_val}}}"
      return rf"\overline{{{e_val}}}"
  ```

### `func`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:func`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_func](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L282)

- **Conversion**

  ```python
  def _handle_func(elem: ET.Element) -> str:
      fname_text = _func_name(elem)
      func_cmd = _FUNC_MAP.get(fname_text, rf"\operatorname{{{fname_text}}}")
  
      lim = _child_convert(elem, "lim")
      e_val = _child_convert(elem, "e")
  
      result = func_cmd
      if lim:
          result += f"_{{{lim}}}"
      if e_val:
          result += f"{{{e_val}}}"
      return result
  ```

### `groupChr`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:groupChr`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_groupchr](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L310)

- **Conversion**

  ```python
  def _handle_groupchr(elem: ET.Element) -> str:
      chr_val = _child_attr(elem, "pr", "chr") or _child_attr(elem, "groupChrPr", "chr")
      e_val = _child_convert(elem, "e")
      if chr_val is not None:
          return rf"\overbrace{{{e_val}}}" if chr_val == "⏞" else f"{{{e_val}}}"
      return f"{{{e_val}}}"
  ```

### `d`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:d`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_d](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L322)

- **Conversion**

  ```python
  def _handle_d(elem: ET.Element) -> str:
      beg_chr = _child_attr(elem, "pr", "begChr") or "("
      end_chr = _child_attr(elem, "pr", "endChr") or ")"
      beg = _DELIM_MAP.get(beg_chr, beg_chr)
      end = _DELIM_MAP.get(end_chr, end_chr)
      e_val = _child_convert(elem, "e")
      return rf"\left{beg} {e_val} \right{end}"
  ```

### `m`

- **Output**
  - LaTeX fragment in the containing equation.

- **OOXML**
  - `m:m`

- **IR**
  - Recursive string result.

- **Parsing**
  - [_handle_m](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L335)

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
  - [_handle_eqarr](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L348)

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
  - [_handle_limlow](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L358)

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
  - [_handle_limupp](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L365)

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
  - [_handle_phant](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L375)

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
  - [_handle_borderbox](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L381)

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
  - [_handle_box](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L387)

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
  - [_convert_children](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L411)

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
  - [_convert_children](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L411)

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
  - [_convert_children](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L411)

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
  - [_convert_children](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L411)

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
  - [_convert_children](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L411)

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
  - [_convert_children](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L411)

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
  - [_convert_children](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L411)

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
  - [_convert_children](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L411)

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
  - [_convert_children](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L411)

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
  - `lambda e: _plain_text(e).strip()`

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

- [_escape_latex](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L438)
- [_plain_text](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L432)
- [_wrap_group](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L421)
- [_child_attr](../../packages/ooxml_llm_core/src/ooxml_llm_core/omml_latex.py#L403)
