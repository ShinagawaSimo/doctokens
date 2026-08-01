"""OMML (Office Math Markup Language) → LaTeX 转换器。

将 Word 文档中的公式子树递归转换为标准 LaTeX 数学表达式。
覆盖约 25 种 OMML 元素：分式、根号、上下标、n-ary 运算符、
重音、函数名、括号组、矩阵、方程组、极限、幻影等。
"""

from __future__ import annotations

from collections.abc import Callable
from xml.etree import ElementTree as ET

from ..core.constants import attr, child_elements, first_child, local_name, qualified_name

# ── N-ary 运算符映射 ──
# <m:chr> 的 Unicode 字符值 → LaTeX 命令
_NARY_OPERATOR_MAP: dict[str, str] = {
    "∑": r"\sum",  # ∑
    "∏": r"\prod",  # ∏
    "∐": r"\coprod",  # ∐
    "∫": r"\int",  # ∫
    "∬": r"\iint",  # ∬
    "∭": r"\iiint",  # ∭
    "∮": r"\oint",  # ∮
    "⋃": r"\bigcup",  # ⋃
    "⋂": r"\bigcap",  # ⋂
    "⋀": r"\bigwedge",  # ⋀
    "⋁": r"\bigvee",  # ⋁
    "⨀": r"\bigodot",  # ⨀
    "⨁": r"\bigoplus",  # ⨁
    "⨂": r"\bigotimes",  # ⨂
}

# ── 重音映射 ──
# <m:acc> 的 <m:chr> 值 → LaTeX 重音命令
_ACCENT_MAP: dict[str, str] = {
    "̂": r"\hat",  # 抑扬符  ̂
    "̃": r"\tilde",  # 波浪线  ̃
    "̇": r"\dot",  # 点      ̇
    "̈": r"\ddot",  # 双点    ̈
    "⃗": r"\vec",  # 向量箭头 ⃗
    "̄": r"\bar",  # 上划线  ̄
    "̆": r"\breve",  # 短音符  ̆
    "̌": r"\check",  # 抑扬符  ̌
    "̀": r"\grave",  # 重音符  ̀
    "́": r"\acute",  # 尖音符  ́
}

# ── 数学函数映射 ──
# <m:func> 的 <m:fName> 文本 → LaTeX 函数命令
_FUNC_MAP: dict[str, str] = {
    "sin": r"\sin",
    "cos": r"\cos",
    "tan": r"\tan",
    "csc": r"\csc",
    "sec": r"\sec",
    "cot": r"\cot",
    "sinh": r"\sinh",
    "cosh": r"\cosh",
    "tanh": r"\tanh",
    "arcsin": r"\arcsin",
    "arccos": r"\arccos",
    "arctan": r"\arctan",
    "log": r"\log",
    "ln": r"\ln",
    "lg": r"\lg",
    "exp": r"\exp",
    "max": r"\max",
    "min": r"\min",
    "sup": r"\sup",
    "inf": r"\inf",
    "lim": r"\lim",
    "limsup": r"\limsup",
    "liminf": r"\liminf",
    "det": r"\det",
    "gcd": r"\gcd",
    "deg": r"\deg",
    "dim": r"\dim",
    "hom": r"\hom",
    "ker": r"\ker",
    "arg": r"\arg",
    "mod": r"\mod",
    "Pr": r"\Pr",
}

# ── 括号/定界符映射 ──
# <m:dPr> 的 begChr/endChr 字符 → LaTeX 定界符
_DELIM_MAP: dict[str, str] = {
    "(": "(",
    ")": ")",
    "[": "[",
    "]": "]",
    "{": r"\{",
    "}": r"\}",
    "|": "|",
    "‖": r"\|",  # ‖ 双竖线
    "⌊": r"\lfloor",  # ⌊
    "⌋": r"\rfloor",  # ⌋
    "⌈": r"\lceil",  # ⌈
    "⌉": r"\rceil",  # ⌉
    "⟨": r"\langle",  # ⟨
    "⟩": r"\rangle",  # ⟩
}


def omath_to_latex(elem: ET.Element) -> str:
    """将 OMML 公式元素树递归转换为 LaTeX 字符串。
    LaTeX 数学模式下空格被忽略，因此直接拼接即可。"""
    parts: list[str] = []
    for child in elem:
        latex = _convert_node(child)
        if latex:
            parts.append(latex)
    return "".join(parts)


def _convert_node(node: ET.Element) -> str:
    """按节点标签名分发到对应的处理函数。"""
    lname = local_name(node.tag)
    handler = _DISPATCH.get(lname)
    if handler is not None:
        return handler(node)
    # 未知元素：尝试提取其中文本
    return _plain_text(node)


# ── 叶子节点：数学文本 run ──


def _handle_r(elem: ET.Element) -> str:
    """处理 <m:r>：提取格式化文本并转义 LaTeX 特殊字符。"""
    parts: list[str] = []
    for child in elem:
        if local_name(child.tag) == "t":
            text = child.text or ""
            parts.append(_escape_latex(text))
    return "".join(parts)


def _handle_t(elem: ET.Element) -> str:
    """处理 <m:t>（可能被递归调用时直接遇到）。"""
    return _escape_latex(elem.text or "")


# ── 分式 ──


def _handle_f(elem: ET.Element) -> str:
    """处理 <m:f> → \\frac{num}{den}。"""
    num = _child_convert(elem, "num")
    den = _child_convert(elem, "den")
    return rf"\frac{{{num}}}{{{den}}}"


# ── 根号 ──


def _handle_rad(elem: ET.Element) -> str:
    """处理 <m:rad> → \\sqrt[deg]{e}。"""
    deg = _child_convert(elem, "deg")
    e_val = _child_convert(elem, "e")
    if deg:
        return rf"\sqrt[{deg}]{{{e_val}}}"
    return rf"\sqrt{{{e_val}}}"


# ── 上下标 ──


def _handle_ssub(elem: ET.Element) -> str:
    """处理 <m:sSub> → {e}_{sub}。"""
    e_val = _child_convert(elem, "e")
    sub = _child_convert(elem, "sub")
    e_out = _wrap_group(e_val)
    return f"{e_out}_{{{sub}}}"


def _handle_ssup(elem: ET.Element) -> str:
    """处理 <m:sSup> → {e}^{sup}。"""
    e_val = _child_convert(elem, "e")
    sup = _child_convert(elem, "sup")
    e_out = _wrap_group(e_val)
    return f"{e_out}^{{{sup}}}"


def _handle_ssubsup(elem: ET.Element) -> str:
    """处理 <m:sSubSup> → {e}_{sub}^{sup}。"""
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


def _handle_spre(elem: ET.Element) -> str:
    """处理 <m:sPre> → {}_{sub}^{sup}{e}。"""
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


# ── N-ary 运算符（求和、积分、乘积等） ──


def _handle_nary(elem: ET.Element) -> str:
    """处理 <m:nary> → \\sum_{sub}^{sup} 或 \\int_{sub}^{sup} 等。"""
    # 从 <m:chr> 读取运算符字符
    chr_val = _child_attr(elem, "chr", "val")
    op = _NARY_OPERATOR_MAP.get(chr_val or "", r"\sum")

    sub = _child_convert(elem, "sub")
    sup = _child_convert(elem, "sup")
    e_val = _child_convert(elem, "e")

    # 构建 limits
    limits = ""
    if sub:
        limits += f"_{{{sub}}}"
    if sup:
        limits += f"^{{{sup}}}"

    return f"{op}{limits} {{{e_val}}}"


# ── 重音 ──


def _handle_acc(elem: ET.Element) -> str:
    """处理 <m:acc> → \\hat{e}、\\vec{e} 等。"""
    chr_val = _child_attr(elem, "chr", "val")
    cmd = _ACCENT_MAP.get(chr_val or "", r"\hat")
    e_val = _child_convert(elem, "e")
    return f"{cmd}{{{e_val}}}"


# ── 上下划线 ──


def _handle_bar(elem: ET.Element) -> str:
    """处理 <m:bar> → \\overline{e} 或 \\underline{e}。"""
    pos = _child_attr(elem, "pr", "pos") or "top"
    e_val = _child_convert(elem, "e")
    if pos == "bot":
        return rf"\underline{{{e_val}}}"
    return rf"\overline{{{e_val}}}"


# ── 数学函数 ──


def _handle_func(elem: ET.Element) -> str:
    """处理 <m:func> → \\sin{e} 或 \\lim_{sub} e。"""
    fname_text = _func_name(elem)
    func_cmd = _FUNC_MAP.get(fname_text, rf"\operatorname{{{fname_text}}}")

    # 检查是否有 limits（如 lim 的 subscript）
    lim = _child_convert(elem, "lim")
    e_val = _child_convert(elem, "e")

    result = func_cmd
    if lim:
        result += f"_{{{lim}}}"
    if e_val:
        result += f"{{{e_val}}}"
    return result


def _func_name(elem: ET.Element) -> str:
    """从 <m:fName> 中提取函数名文本。"""
    fname = first_child(elem, "m", "fName")
    if fname is None:
        return ""
    return _plain_text(fname).strip()


# ── 括号组 ──


def _handle_groupchr(elem: ET.Element) -> str:
    """处理 <m:groupChr> → {e} 或上方有符号的括号组。"""
    chr_val = _child_attr(elem, "pr", "chr") or _child_attr(elem, "groupChrPr", "chr")
    e_val = _child_convert(elem, "e")
    if chr_val is not None:
        return rf"\overbrace{{{e_val}}}" if chr_val == "⏞" else f"{{{e_val}}}"
    return f"{{{e_val}}}"


# ── 定界符（括号） ──


def _handle_d(elem: ET.Element) -> str:
    """处理 <m:d> → \\left( e \\right)。"""
    beg_chr = _child_attr(elem, "pr", "begChr") or "("
    end_chr = _child_attr(elem, "pr", "endChr") or ")"
    beg = _DELIM_MAP.get(beg_chr, beg_chr)
    end = _DELIM_MAP.get(end_chr, end_chr)
    e_val = _child_convert(elem, "e")
    return rf"\left{beg} {e_val} \right{end}"


# ── 矩阵 ──


def _handle_m(elem: ET.Element) -> str:
    """处理 <m:m>（矩阵）→ \\begin{matrix}...\\end{matrix}。"""
    rows: list[str] = []
    for mr in child_elements(elem, "m", "mr"):
        cells = [_convert_node(cell) for cell in mr if local_name(cell.tag) == "e"]
        rows.append(" & ".join(cells))
    body = r" \\ ".join(rows)
    return rf"\begin{{matrix}} {body} \end{{matrix}}"


# ── 方程组 ──


def _handle_eqarr(elem: ET.Element) -> str:
    """处理 <m:eqArr> → \\begin{aligned}...\\end{aligned}。"""
    rows = [_convert_node(child) for child in elem if local_name(child.tag) == "e"]
    body = r" \\ ".join(rows)
    return rf"\begin{{aligned}} {body} \end{{aligned}}"


# ── 极限 ──


def _handle_limlow(elem: ET.Element) -> str:
    """处理 <m:limLow> → {e}_{lim}。"""
    e_val = _child_convert(elem, "e")
    lim = _child_convert(elem, "lim")
    return f"{{{e_val}}}_{{{lim}}}"


def _handle_limupp(elem: ET.Element) -> str:
    """处理 <m:limUpp> → {e}^{lim}。"""
    e_val = _child_convert(elem, "e")
    lim = _child_convert(elem, "lim")
    return f"{{{e_val}}}^{{{lim}}}"


# ── 幻影/边框盒/空盒 ──


def _handle_phant(elem: ET.Element) -> str:
    """处理 <m:phant> → \\phantom{e}。"""
    e_val = _child_convert(elem, "e")
    return rf"\phantom{{{e_val}}}"


def _handle_borderbox(elem: ET.Element) -> str:
    """处理 <m:borderBox> → \\boxed{e}。"""
    e_val = _child_convert(elem, "e")
    return rf"\boxed{{{e_val}}}"


def _handle_box(elem: ET.Element) -> str:
    """处理 <m:box>：直接传递子元素。"""
    return _convert_children(elem)


# ── 辅助函数 ──


def _child_convert(elem: ET.Element, child_local: str) -> str:
    """查找指定 local name 的第一个子元素并转换，不存在时返回空串。"""
    child = first_child(elem, "m", child_local)
    if child is None:
        return ""
    return _convert_node(child)


def _child_attr(elem: ET.Element, child_local: str, attr_name: str) -> str | None:
    """读取指定子元素的 m:val 属性值。"""
    child = first_child(elem, "m", child_local)
    if child is None:
        return None
    return attr(child, "m", attr_name)


def _convert_children(elem: ET.Element) -> str:
    """转换所有子元素并直接拼接（LaTeX 数学模式忽略空格）。"""
    parts: list[str] = []
    for child in elem:
        latex = _convert_node(child)
        if latex:
            parts.append(latex)
    return "".join(parts)


def _wrap_group(latex: str) -> str:
    """如果 LaTeX 包含分式/根号/多字符等需要显式分组的情况，加上花括号。"""
    if not latex:
        return "{}"
    if any(cmd in latex for cmd in (r"\frac", r"\sqrt", r"\sum", r"\int", r"\prod")):
        return f"{{{latex}}}"
    if " " in latex or len(latex) > 1:
        return f"{{{latex}}}"
    return latex


def _plain_text(elem: ET.Element) -> str:
    """提取元素内所有 <m:t> 文本（fallback 用）。"""
    parts = [mt.text for mt in elem.iter(qualified_name("m", "t")) if mt.text]
    return "".join(parts)


def _escape_latex(text: str) -> str:
    """转义 LaTeX 特殊字符。"""
    # 转义顺序重要：先处理反斜杠，再处理花括号
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for char, repl in replacements:
        text = text.replace(char, repl)
    return text


# ── 元素分发表 ──

_DISPATCH: dict[str, Callable[[ET.Element], str]] = {
    "r": _handle_r,
    "t": _handle_t,
    "f": _handle_f,
    "rad": _handle_rad,
    "sSub": _handle_ssub,
    "sSup": _handle_ssup,
    "sSubSup": _handle_ssubsup,
    "sPre": _handle_spre,
    "nary": _handle_nary,
    "acc": _handle_acc,
    "bar": _handle_bar,
    "func": _handle_func,
    "groupChr": _handle_groupchr,
    "d": _handle_d,
    "m": _handle_m,
    "eqArr": _handle_eqarr,
    "limLow": _handle_limlow,
    "limUpp": _handle_limupp,
    "phant": _handle_phant,
    "borderBox": _handle_borderbox,
    "box": _handle_box,
    # 容器元素：透传子元素
    "oMath": _convert_children,
    "oMathPara": _convert_children,
    # 以下元素直接透传子元素
    "e": _convert_children,
    "num": _convert_children,
    "den": _convert_children,
    "sub": _convert_children,
    "sup": _convert_children,
    "deg": _convert_children,
    "lim": _convert_children,
    "fName": lambda e: _plain_text(e).strip(),
    "chr": lambda e: e.get(qualified_name("m", "val"), ""),
    # 格式控制元素：不产生输出
    "oMathParaPr": lambda e: "",
    "oMathPr": lambda e: "",
    "sSubPr": lambda e: "",
    "sSupPr": lambda e: "",
    "sSubSupPr": lambda e: "",
    "sPrePr": lambda e: "",
    "fPr": lambda e: "",
    "naryPr": lambda e: "",
    "radPr": lambda e: "",
    "accPr": lambda e: "",
    "barPr": lambda e: "",
    "dPr": lambda e: "",
    "mPr": lambda e: "",
    "eqArrPr": lambda e: "",
    "groupChrPr": lambda e: "",
    "ctrlPr": lambda e: "",
    "rPr": lambda e: "",
    "sty": lambda e: "",
    "jc": lambda e: "",
}
