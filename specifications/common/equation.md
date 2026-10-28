# OMML expressions

[COMMON](README.md) / OMML expressions

Native Office Math is projected to LaTeX reading text. The projection preserves
saved mathematical symbols and structure; it does not calculate an expression,
infer the author's definitions, or reconstruct exact typography and geometry.

## Processing

- [Conversion](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/converter.py)
  creates a fresh context per expression. Namespace-qualified math and Word
  content use their own dispatch rules; no document-global state or cache exists.
- `convert_math(element, revision_mode=..., warn=...)` returns a `MathResult`
  containing reading text and nested review ranges. Read `.text` when only the
  LaTeX string is needed. The caller's DOCX revision view participates in
  conversion, independently of reading density.
- Word hyperlink, simple-field, SmartTag, custom-XML and content-control
  wrappers are traversed without flattening their mathematical children.
  Bookmarks, proofing/permission markers and run-property containers add no
  mathematical characters. Field instructions are not evaluated.
- Literal TeX characters are escaped once. Normal text and equation-array
  alignment markers have distinct contexts. Generated commands are not
  re-escaped.
- Unknown semantic elements/namespaces retain escaped descendant math text and
  invoke `MATH_CONTENT_UNSUPPORTED` when a warning sink is supplied. They do not
  silently claim a complete structural conversion. Layout-property containers
  remain intentionally omitted.
- Public DOCX/PPTX adapters attach conversion diagnostics to their ordinary
  parse reports. Unknown font encodings are not guessed.

## Fields

### `r`

- **Output**
  - Converted math-run content.
- **OOXML**
  - `m:r`, or a saved `w:r` inside a math container.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Read direct `m:t`, `w:t` and saved `w:delText` in order; apply explicit math-run properties. Decode supported Word character nodes and explicit breaks. Run text and known-character decoding are in [text.py](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/text.py).

### `t`

- **Output**
  - Escaped text, subject to the containing run's math/text mode.
- **OOXML**
  - `m:t` and the corresponding saved Word text children.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Preserve source characters. Literal ``, braces, `_`, `&`, `%`, `$`, `#`, `~` and `^` are escaped once; normal-text whitespace remains inside `\text{...}`. Outside array alignment contexts a real ampersand remains literal `\&`.

### `scr`

- **Output**
  - Unicode mathematical letters, including Letterlike Symbols where Unicode has historical holes.
- **OOXML**
  - `m:r/m:rPr/m:scr/@m:val`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Decode ASCII letters/digits using the declared script: `script`, `fraktur`, `double-struck`, `sans-serif`, or `monospace`. Existing non-ASCII symbols and operators are retained. For example, saved ASCII `R` with double-struck becomes `ℝ`; fraktur `g` becomes `𝔤`. An omitted script element or value uses roman. Unsupported script names invoke `MATH_SCRIPT_UNSUPPORTED` and keep escaped text.

### `sty`

- **Output**
  - Explicit reading style on mathematical letters.
- **OOXML**
  - `m:r/m:rPr/m:sty/@m:val`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Roman script uses `\mathrm`, `\mathbf`, `\mathit`, or `\boldsymbol` for `p`, `b`, `i`, `bi`. Non-roman alphabets choose their Unicode bold/italic variants where those exist. Unspecified style does not add a roman wrapper; the non-roman mapping uses italic as its default style choice. Unsupported roman style invokes `MATH_STYLE_UNSUPPORTED`.

### `nor`

- **Output**
  - `\text{...}` for normal-text runs.
- **OOXML**
  - `m:r/m:rPr/m:nor/@m:val`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Missing means false. A present flag without `val` means true; `0`, `false`, `off` mean false. Keep actual words and spaces separate from mathematical variables. Example: `if x > 0` → `\text{if x > 0}`. Its genuine ampersands remain literal even inside an equation array.

### `f`

- **Output**
  - A fraction or a no-bar stack.
- **OOXML**
  - `m:f/m:num`, `m:f/m:den` and `m:f/m:fPr/m:type`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Convert numerator and denominator recursively. A `noBar` object uses `\genfrac{}{}{0pt}{}{numerator}{denominator}`. Other fraction layouts (`bar`, `lin`, `skw`) share `\frac{numerator}{denominator}` as a reading representation. A no-bar stack is not automatically interpreted as a binomial coefficient. See [structures.py](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/structures.py).

### `rad`

- **Output**
  - `\sqrt{base}` or `\sqrt[degree]{base}`.
- **OOXML**
  - `m:rad/m:deg`, `m:rad/m:e`, `m:rad/m:radPr/m:degHide`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Honor `degHide` before reading the saved degree. Missing flag is false; a present flag without `val` is true. A hidden or empty degree produces a square-root reading. A nonempty visible degree is retained. Hidden saved `3` must not change the visible square root into a cube root.

### `sSub`

- **Output**
  - Grouped base followed by `_{subscript}`.
- **OOXML**
  - `m:sSub/{m:e,m:sub}`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Convert the base and subscript recursively; group a compound base before attaching its script.

### `sSup`

- **Output**
  - Grouped base followed by `^{superscript}`.
- **OOXML**
  - `m:sSup/{m:e,m:sup}`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Convert the base and exponent recursively. Nested powers attach to grouped intermediate expressions, rather than emitting consecutive ungrouped superscripts.

### `sSubSup`

- **Output**
  - Grouped base, optional lower script and optional upper script.
- **OOXML**
  - `m:sSubSup/{m:e,m:sub,m:sup}`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Convert each argument recursively. Preserve both scripts without using their exact source alignment as a separate output field.

### `sPre`

- **Output**
  - `{}_{lower}^{upper}base`.
- **OOXML**
  - `m:sPre/{m:sub,m:sup,m:e}`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - The left scripts have their own empty TeX base. They must not attach to a preceding source character; for example `x{}_{l}^{u}A`.

### `nary`

- **Output**
  - Saved operator, visible limits, then its grouped operand.
- **OOXML**
  - `m:nary/m:naryPr/{m:chr,m:subHide,m:supHide}` and direct `m:sub`, `m:sup`, `m:e`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Read `chr/@m:val` at its standard property level. Missing `chr` defaults to integral U+222B; a present empty character means no operator. Map known operators through `_NARY_OPERATOR_MAP`, preserving other explicit characters. Hide each limit only when its corresponding flag is true. An empty operator with limits uses `{}` as its TeX base. Example: `∏`, `k=1`, `n`, `A` → `\prod_{k=1}^{n} {A}`. See [operators.py](../../packages/doctokens_core/src/doctokens_core/ooxml/equations/operators.py).

### `acc`

- **Output**
  - A known accent command, or a preserved explicit accent character.
- **OOXML**
  - `m:acc/m:accPr/m:chr/@m:val` and direct `m:e`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Missing character defaults to combining circumflex U+0302. A present empty character leaves the base undecorated. Known vector/dot/tilde/hat characters use `_ACCENT_MAP`; other explicit characters use `\overset{character}{base}`. Example: vector `v` → `\vec{v}`.

### `bar`

- **Output**
  - `\overline{base}` or `\underline{base}`.
- **OOXML**
  - `m:bar/m:barPr/m:pos/@m:val` and direct `m:e`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Explicit `top` selects overline; `bot` selects underline. Omitted position or value defaults to `bot`, following ISO/IEC 29500-1:2016 §22.1.2.84 and the Office reading behavior.

### `func`

- **Output**
  - Function name and its recursively converted argument.
- **OOXML**
  - `m:func/m:fName` and direct `m:e`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Map simple textual names using `_FUNC_MAP`, with escaped `\operatorname{...}` for other simple names. Preserve structural function names through their ordinary math handlers, including accents, fractions and delimiters. Preserve scripts and limits on a recursively grouped name. Example: a hat on `f` stays `\hat{f}{x}`.

### `fName`

- **Output**
  - A simple name or an intact compound function-name expression.
- **OOXML**
  - `m:func/m:fName`, an `CT_OMathArg` containing math/Word content.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Handle `limLow`, `limUpp`, `sSub`, `sSup`, `sSubSup`, `sPre` as structural name nodes inside the standard `fName` argument. Group every compound script base. For example `(f²)³` becomes `{\operatorname{f}^{2}}^{3}`. Transparent wrappers and revisions retain the function-name traversal context.

### `groupChr`

- **Output**
  - An over/under brace, arrow or explicit grouping character.
- **OOXML**
  - `m:groupChr/m:groupChrPr/{m:chr,m:pos}` and direct `m:e`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Missing character defaults to U+23DF (bottom curly bracket), and missing position defaults to `bot`. A present empty character leaves the base undecorated. Use `\overbrace`/`\underbrace` for matching upper/lower braces, corresponding arrow commands for arrows, and `\overset`/`\underset` for other explicit character/position pairs. Exact stretching and baseline justification are not reconstructed.

### `d`

- **Output**
  - All arguments in order, with their saved delimiters and separator.
- **OOXML**
  - `m:d/m:dPr/{m:begChr,m:sepChr,m:endChr}` and every direct `m:e`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Omitted beginning/ending characters default to `(`/`)`; omitted separator defaults to `|` (including the U+2502 spelling). A present empty character means no character, not the default. Empty outer delimiters use `\left.`/`\right.`. Known delimiters use `_DELIM_MAP`; custom characters use `\mathopen`/`\mathclose`. Example: two arguments `x`,`y`, square brackets and `;` → `\left[ x;y \right]`.

### `m`

- **Output**
  - `\begin{matrix} ... \end{matrix}`.
- **OOXML**
  - `m:m/m:mr/m:e`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Retain source rows and cells, joining cells with `&` and rows with `\`. Source column widths/justification and exact row spacing are not projected.

### `eqArr`

- **Output**
  - `\begin{aligned} ... \end{aligned}`.
- **OOXML**
  - `m:eqArr/m:e` and mathematical text within each argument.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Retain rows. Count source alignment ampersands across runs within each row: odd occurrences become TeX alignment tabs; even occurrences are adjustable source spacers and are omitted. Reset the counter for each row and nested array. Genuine normal-text ampersands remain escaped literals. Styled runs split around alignment tabs, keeping tabs outside style-command braces.

### `limLow`

- **Output**
  - `{base}_{limit}` outside a function-name context.
- **OOXML**
  - `m:limLow/{m:e,m:lim}`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Keep the base and limit structure. Within a function name, use the recognized function name and grouped compound bases instead of flattening limit text into that name.

### `limUpp`

- **Output**
  - `{base}^{limit}` outside a function-name context.
- **OOXML**
  - `m:limUpp/{m:e,m:lim}`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - The same recursive rules as lower limits apply, with the upper-script marker.

### `phant`

- **Output**
  - Visible base or explicit `\phantom{base}`.
- **OOXML**
  - `m:phant/m:phantPr/m:show` and direct `m:e`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - `show` defaults to true, including when present without `val`. Return the visible base when true; use `phantom` only for false. Exact zero-width/ascent/descent and transparency layout are not reconstructed.

### `borderBox`

- **Output**
  - Saved enclosure/strike states, as a reading projection.
- **OOXML**
  - `m:borderBox/m:borderBoxPr` and direct `m:e`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - All four visible edges use `\boxed`. With hidden edges, visible top/bottom edges use overline/underline and visible left/right edges use paired `\left\lvert`/`\right\rvert` or invisible partners. This retains the selected edges without promising exact line joins. Forward/backward/both diagonal strikes use `\cancel`, `\bcancel`, `\xcancel`. Horizontal/vertical strikes use explicit `\overset{\text{horizontal strike}}{...}` / `vertical strike` reading annotations, not guessed diagonal cancellation. A flag is false when absent and true when present without a value.

### `box`

- **Output**
  - Converted children.
- **OOXML**
  - `m:box/m:e` and its property container.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Read content recursively. Operator-emulation spacing, automatic line-wrap constraints and differential spacing are layout properties, not a reason to change the saved operator/letters.

### `oMath`

- **Output**
  - One mathematical expression.
- **OOXML**
  - `m:oMath`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Convert children in source order. Known transparent Word containers are traversed as structure; unknown semantic content reports conversion degradation.

### `oMathPara`

- **Output**
  - One expression, or `\begin{gathered} ... \\ ... \end{gathered}`.
- **OOXML**
  - `m:oMathPara/m:oMath`.
- **IR**
  - Recursive string result in the containing equation.
- **Parsing**
  - Keep independent expression boundaries. One retained expression needs no extra environment; multiple expressions use gathered. Revision filtering can remove an empty expression. Explicit hard breaks within an argument also use gathered, while automatic line layout remains outside this projection.

## Word content and revisions

### `revision_mode`

- **Output**
  - DOCX uses the selected view in all densities. Semantic review additionally
    emits `ins`/`del` children within an equation or around a whole equation.
- **OOXML**
  - Word `ins`, `moveTo`, `del`, `moveFrom` wrappers.
- **IR**
  - Internal `MathResult.text` plus nested `MathRevision` ranges. These are not
    source offsets or an editable projection.
- **Parsing**
  - `final` retains insertions/move destinations; `original` retains
    deletions/move sources; `review` retains both and reviewer attribution.
  - Keep formula structure inside a retained wrapper. Deleted whole formulas
    are recovered as formula objects instead of concatenated deleted letters.
  - Semantic review markup is mixed XML content: concatenate an equation's
    character data with `itertext()` to recover its complete LaTeX text.
    Structural/plain review contains both saved branches without attribution
    wrappers, consistent with its lower density.
  - Example: `<equation notation="latex">\frac{<ins author="A">a</ins>}{b}</equation>`.
  - A fresh conversion context owns these ranges; internal composition markers
    never appear in output.
- **Diagnostics**
  - Invalid internal view value: `ValueError`.

### `word_characters`

- **Output**
  - Known text characters, `quad` for a tab, or explicit gathered-line boundaries.
- **OOXML**
  - Word `noBreakHyphen`, `softHyphen`, `tab`, `br`, `cr`, `sym` inside math runs.
- **IR**
  - Converted string fragments.
- **Parsing**
  - A nonbreaking hyphen uses `\text{-}` so it remains a text hyphen even when a
    math font lacks U+2011. A discretionary soft-hyphen node adds no visible glyph
    without line layout. Breaks keep explicit boundaries.
  - `sym` in the known Symbol encoding uses the saved hexadecimal code and
    font name. Decode its byte-sized or U+F000-prefixed encoding using the
    Unicode mapping in [symbols.py](../../packages/doctokens_core/src/doctokens_core/ooxml/symbols.py).
    Extender/private glyphs and other font encodings are not guessed.
  - Run properties, field-control instructions and saved page-wrap markers add
    no mathematical characters.
- **Diagnostics**
  - `MATH_SYMBOL_UNSUPPORTED`: unknown font/character mapping.
  - `MATH_RUN_CHILD_UNSUPPORTED`: encountered other unhandled math-run content.

## Deliberate limits

Exact font metrics, source coordinates, mathematical glyph stretching, line joins,
source spacing and automatic page/line layout are not reconstructed. Conversion
does not evaluate Office fields or formulas. Transparent mathematical hyperlink
wrappers preserve mathematical structure; their internal navigation is not a new
public navigation API. Unsupported semantic content is reported when the host
provides a warning sink; reading fallback text does not establish full support.
