# DOCX 解析输出格式说明

本文档面向下游开发者和 LLM tool description 编写者，解释 `docx-llm-parser` 输出的语义 HTML5 标记格式。

## 总体设计

解析器将 `.docx` 文件转化为三种密度的输出：

| 密度 | 枚举值 | 文件 | 内容 |
|---|---|---|---|
| 语义级 | `SEMANTIC` (`"semantic"`) | `parsed.html` | 完整 HTML5 标记，含所有内联格式、对象引用和表格结构 |
| 结构级 | `STRUCTURAL` (`"structural"`) | `structural.html` | 块级结构 + 语义对象，去除粗体/斜体/颜色等视觉格式 |
| 纯文本 | `PLAIN` (`"plain"`) | `plain.txt` | 纯文本流，段落间以空行分隔；脚注拼接到段末，尾注与批注拼接在文末 |

输出第一行标记密度：

```
density=semantic
density=structural
density=plain
```

下文以 semantic 为准介绍完整格式。structural 和 plain 分别是 semantic 的逐级精简。

## 隐式闭合规则

块级元素省略闭合标签。当一个块级元素结束时，由下一个块级元素或文档结束隐式表示。

**隐式闭合的块级元素**：`<h1>`–`<h6>`、`<p>`、`<td>`、`<th>`、`<tr>`、`<chart>`、`<smartart>`

**显式闭合的内联元素**：`<a>`、`<b>`、`<i>`、`<u>`、`<s>`、`<color>`、`<mark>`、`<sup>`、`<sub>`、`<equation>`、`<ins>`、`<del>`、`<textbox>`

```
示例：
<h1>第一章                          ← 无闭合标签
<p>正文内容                          ← 无闭合标签
<b>粗体</b>                         ← 内联元素需要显式闭合
下一段正文                          ← 空行表示段落间距
```

## 段落模型

每个段落独立输出一个 `<p>` 标签，段落之间以空行分隔。

```
<p>第一段内容

<p>第二段内容

<p>第三段内容
<h2>标题                            ← 标题中断了段落流
<p>新段落的开始
```

段落内的软换行（Word 中 Shift+Enter）以单个 `\n` 表示。
段落间的硬换行（Word 中 Enter）以 `\n\n`（空行）表示。

## 块级元素清单

### 标题 `<h1>`–`<h6>`

标题级别仅来自 Word 样式中的 `w:outlineLvl`。不使用字号、加粗等视觉特征推断。

```
<h1>论文标题
<h2>第一章
<h3>1.1 小节标题
```

### 段落 `<p>`

见上文"段落模型"。

### 页标记 `<page=N>`

页码标记出现在发生分页的两个段落/表格之间。页码由 OOXML 中的显式分页标记推导（`w:lastRenderedPageBreak`）。

```
<page=1>
...第一页内容...
<page=2>
...第二页内容...
```

### 表格 `<table>`

```
<table>
<tr header><th>列名1<th>列名2<th colspan=2>列名3
<tr><td>数据1<td>数据2<td>数据3-1<td>数据3-2
```

- `<tr header>` 表示表头行
- `colspan=N` 表示列合并
- `rowspan=N` 表示行合并
- `vmerge=restart` / `vmerge=continue` 表示垂直合并
- 大表格（>30 行）标记 `<table truncated>`，仅输出表头行和首行数据
- 嵌套表格以 `<nestedtable rows=N cols=M>` 包裹，行以 `<row header>` / `<row>` 标记

### 图片 `<img>`

正文中：
```
<img id=img1 alt=描述文字>
```

supplemental 区（资产索引）：
```
<img id=img1 href=assets/img1_a1b2c3d4.png>
```

- `id`：图片 id
- `alt`：图片的替代文本（来自 OOXML `descr` 属性）
- `href`：导出的文件路径（相对于输出目录，仅在 supplemental 区出现）

### 图表 `<chart>`

```
<chart id=chart1 type=bar title=人口趋势 series=2 categories=一期,二期 names=人群A,人群B truncated>
```

- `id`：图表标识符
- `type`：图表类型（bar/line/pie/scatter/bubble/area/radar/surface 等）
- `title`：图表标题（可选，仅非空时输出）
- `series`：系列数
- `categories`：X 轴标签（逗号分隔，最多 8 个；饼图为扇区名称）
- `names`：系列名称（逗号分隔）
- `points`：总数据点数（散点图/气泡图）
- 所有图表均标记 `truncated`，完整数据点通过 `get_resource(parsed, "chart", "chart1")` 获取

### SmartArt `<smartart>`

```
<smartart id=smartart1 type=process nodes=8 links=7 truncated>
第一步 判断条件 执行操作 ...
```

- `id`：标识符
- `type`：布局类型（process/cycle/hierarchy/list/relationship/matrix/pyramid）
- `nodes`：节点数
- `links`：边数
- 正文显示全部节点文本（空格分隔）
- 总是标记 `truncated`，完整结构通过 `get_resource(parsed, "smartart", "smartart1")` 获取（含节点类型和边关系）

### 文本框 `<textbox>`

```
<textbox alt=描述>文本框内的文字内容</textbox>
```

### 嵌入对象 `<embedded>`

```
<embedded type=excel name="季度数据.xlsx">
```

- `type` 取值：`excel`、`word`、`powerpoint`、`pdf`、`visio`、`image`、`package`、`unknown`
- 不解析嵌入对象内部内容

## 内联元素清单

### 文本格式

```
<b>粗体</b>
<i>斜体</i>
<u>下划线</u>
<s>删除线</s>
<sup>上标</sup>
<sub>下标</sub>
```

### 颜色与高亮

```
<color value=#FF0000>红色文字</color>
<mark value=#FFFF00>黄色高亮</mark>
<mark value=#000000>黑色背景</mark>
```

`color` 用于文字颜色，`mark` 用于高亮和背景色。`value` 为 CSS 颜色值。

### 超链接 `<a>`

```
<a href=https://example.com>链接文字</a>
<a href=#_Toc12345 anchor=_Toc12345>内部书签</a>
```

`href`：外部链接 URL 或内部书签，`anchor`：书签锚点名称。

### 公式 `<equation>`

```
<equation>x^{2} + y^{2} = z^{2}</equation>
```

公式内容为 OMML 转 LaTeX 的结果。支持分式（`\frac`）、根号（`\sqrt`）、上下标（`^{}` `_{}`）、求和（`\sum`）、积分（`\int`）、矩阵（`\begin{matrix}`）等约 25 种 OMML 元素。

### 引用标记

```
<footnoteref id=1/>
<endnoteref id=2/>
<commentref id=3/>
```

### 修订追踪

```
<ins>插入的文本</ins>
<del>删除的文本</del>
<ins author=张三 date=2024-03-15>带作者和日期的插入</ins>
```

### 域指令 `<field>`

```
<field instruction="HYPERLINK https://example.com"/>
<field instruction="PAGEREF _Ref123 \h"/>
<field instruction=" REF _Ref456 \h "/>
```

### 图片（内联） `<img>`

见块级元素清单。

## 补充内容区域 `<!-- supplemental -->`

正文结束后，依次输出页眉、页脚、脚注、尾注、批注的完整内容：

```
<!-- supplemental -->
<header id=hdr1 loc=header1.xml>页眉文字
<footer id=ftr1 loc=footer1.xml>页脚文字
<footnote id=1>脚注正文
<endnote id=2>尾注正文
<comment id=3 author=作者 date=2024-01-15>批注正文
```

- `id`：标识符
- `loc`：来源 part 路径（仅 header/footer）
- `author`、`date`：作者和日期（comment、revision 的可选属性）
- structural 密度不输出 header/footer

## 密度差异对照

| 元素 | semantic | structural | plain |
|---|---|---|---|
| 标题 | `<h1>`–`<h6>` | `<h1>`–`<h6>` | 退化为普通段落（`\n\n` 分隔） |
| 段落 | `<p>` + `\n\n` | 同 semantic | 纯文本 `\n\n` |
| 段落内换行 | `\n` | `\n` | `\n` |
| 粗体/斜体/颜色等 | `<b>` `<i>` `<color value=>` 等 | 全部去除 | 无 |
| 表格 | 完整 HTML 表格 + 合并单元格 | 完整 HTML 表格 + 合并单元格 | `\t` 分隔纯文本，>10 行截断 |
| 表格截断阈值 | 30 行 | 30 行 | 10 行 |
| 图表 | `<chart>` + 属性 + `truncated` | 同 semantic | `[Chart: ...]` 纯文本摘要 |
| SmartArt | `<smartart>` + 属性 + 全部节点文本 | 同 semantic | `[SmartArt ...]` 纯文本摘要 |
| 图片 | `<img id=... alt=...>` | `<img>` 占位 | `[Image]` |
| 嵌入对象 | `<embedded>` + type/name | `<embedded>` + type/name | 不输出 |
| 文本框 | `<textbox alt=...>` + 文字 | 同 semantic | 文字直接融入正文流 |
| 公式 | `<equation>` 内容 | `<equation>` 内容 | 文字直接融入正文流 |
| 脚注 | `<footnoteref/>` + supplemental | 同 semantic | 拼接到段末 `[fnN: content]` |
| 尾注 | `<endnoteref/>` + supplemental | 同 semantic | 拼接到文末 `[edN: content]` |
| 页码 | `<page=N>` | `<page=N>` | 无 |
| 页眉/页脚 | supplemental 区 | 不输出 | 不输出 |
| 批注 | `<commentref/>` + supplemental | `<commentref/>` + supplemental | 拼接到文末 `[cmtN: content]` |

## 资源提取 API

正文中被截断的资源（`<table truncated>`、`<chart ... truncated>`、`<smartart ... truncated>`）可通过 `get_resource` 按需获取完整数据：

### 单资源详情

| 调用 | 返回 |
|---|---|
| `get_resource(parsed, ResourceType.TABLE, "t1")` | 完整表格（合并分页片段，含 rows 数组） |
| `get_resource(parsed, ResourceType.TABLE, "t1", rows="10-25")` | 指定行范围（1-based，含起止行） |
| `get_resource(parsed, ResourceType.TABLE, "t1", columns=["金额","日期"])` | 仅指定列（按表头名称匹配） |
| `get_resource(parsed, ResourceType.TABLE, "t1", aggregate="sum", aggregate_column="金额")` | 聚合值。支持 sum/count/avg/min/max |
| `get_resource(parsed, ResourceType.CHART, "chart1")` | 完整图表数据点（缓存数据） |
| `get_resource(parsed, ResourceType.SMARTART, "smartart1")` | 完整节点和连接列表 |
| `get_resource(parsed, ResourceType.IMAGE, "img1")` | 图片 bytes（含 contentType） |

`rows` 和 `columns` 可组合使用。`aggregate` 基于表格文本中的数值计算，不做公式重算。Chart 和 SmartArt 也可通过 structural/semantic 输出的 `get_resource` 入口获取完整数据，无需先读全文。

## 特殊约定

- 所有方括号标记（如 `[fn1]`、`[Image]`、`[Chart: ...]`）是 plain 专用的纯文本占位符，不出现在 structural/semantic 中
- `<br>` 标签已被 `\n` 替代，不在任何密度中出现
- 表格 id（`tableId`）在解析阶段分配，同篇文档多次解析结果一致
- 属性值含空格或特殊字符时使用双引号包裹并进行 HTML 转义

## 列表编号

列表段落保留 Word 计算后的可见编号文本。编号来自 `w:numPr`、关联的 `w:num` / `w:abstractNum`、`w:lvl` 与 `w:lvlText`；`%1` 至 `%9` 按引用级别替换。`w:numFmt=none` 保留列表层级但不写入可见标记。semantic 密度只在段落上输出一个 `numbering` 标记，让模型知道段首包含解析出的编号；编号本身已经是段首可见文本，不重复暴露格式、层级或内部计数信息。其它密度只保留可见文本。

编号状态按 Word 的重排版语义处理：`w:isLgl` 把当前级别引用的编号按十进制显示；`w:lvlRestart` 使用从 1 开始的级别号，值为 0 表示不重启，省略时按紧邻的上一级及更高层级重启，且 `lvlOverride` 中的 `lvlRestart` 忽略。`w:numStyleLink` 会通过 `styles.xml` 中的编号样式 `numId` 解析到被链接的编号级别。`w:lvlText` 中的 `%%` 保留为字面量 `%`。

项目符号的可见字符与 `w:lvl/w:rPr` 中的颜色、加粗、斜体等格式会进入 semantic 输出。字体不是解析结果的一部分：不会写入 run、block、debug JSON 或 HTML。图片项目符号的 `w:lvlPicBulletId` 会解析为 `word/numbering.xml` 关系中的图片资产，并在段首输出 `<img>`。

上述行为与成熟的原始 OOXML 导入/重排版实现保持同一方向：LibreOffice writerfilter 对缺失 `ilvl` 的有效 `numId` 按 0 级处理，并区分级别重启与样式绑定；ONLYOFFICE core 直接从 Docx OOXML 入口加载 Numbering 模块。实现依据 Microsoft 的 `lvlRestart`、`isLgl` 和 `numStyleLink` 规范，而不是依赖编号显示文本猜测。

### 中文编号

`ideographDigital` 是逐字数字形式：零为 `〇`，多位数字直接拼接，`12345` 产出 `一二三四五`，`102` 产出 `一〇二`。`chineseCounting` 和 `chineseCountingThousand` 是中文数位读法，使用 `十/百/千/万`，中间零使用 `〇`，例如 `1010` 为 `一千〇一十`、`10050` 为 `一万〇五十`。当前夹具矩阵把这三种 XML 值分开登记；文件名不能代替解压后对 `w:numFmt/@w:val` 的确认。

Microsoft 的互操作说明指出，Word 对 `chineseCountingThousand` 在 `10,000` 至 `100,000` 的部分非整千值可能省略 U+96F6；若后续真实文件确认该行为，应以该 golden 为准调整该枚举的 Word 兼容分支，而不能把它泛化到 `ideographDigital`。详见 [MS-OI29500 17.18.59](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/ea3612c8-a099-46c3-99a9-93658a30cb01)。

### 已实现的 `w:numFmt`

| 类别 | 枚举值 |
| --- | --- |
| 拉丁与十进制 | `decimal`、`decimalHalfWidth`、`decimalZero`、`decimalFullWidth`、`decimalFullWidth2`、`upperLetter`、`lowerLetter`、`upperRoman`、`lowerRoman`、`ordinal`、`cardinalText`、`ordinalText`、`hex`、`numberInDash`、`chicago` |
| 围排数字 | `decimalEnclosedCircle`、`decimalEnclosedFullstop`、`decimalEnclosedParen`、`decimalEnclosedCircleChinese`、`ideographEnclosedCircle` |
| 东亚 | `ideographDigital`、`chineseCounting`、`chineseCountingThousand`、`chineseLegalSimplified`、`ideographLegalTraditional`、`japaneseCounting`、`japaneseDigitalTenThousand`、`japaneseLegal`、`taiwaneseCounting`、`taiwaneseCountingThousand`、`taiwaneseDigital`、`koreanDigital`、`koreanCounting`、`ideographZodiac`、`ideographZodiacTraditional` |
| 日韩印泰俄 | `aiueo`、`aiueoFullWidth`、`iroha`、`irohaFullWidth`、`ganada`、`chosung`、`hindiVowels`、`hindiConsonants`、`hindiNumbers`、`thaiLetters`、`thaiNumbers`、`russianLower`、`russianUpper` |
| 希伯来与阿拉伯 | `hebrew1`、`hebrew2`、`arabicAlpha`、`arabicAbjad` |
| 特殊 | `bahtText`、`dollarText`、`bullet`、`none` |

`upperLetter` / `lowerLetter` 按 Word 的重复字符规则编号：`a` 至 `z` 后为 `aa`、`bb`、`cc`，不是 Excel 的 `aa`、`ab`、`ac`。`ganada`、`chosung`、`aiueo`、`iroha` 超过各自字符集时按 Word 行为从第一项重新开始；`hindiVowels` 与 `hindiConsonants` 按 Word 已知的互换实现。

`cardinalText` 和 `ordinalText` 输出英文首字母大写的文字编号（`One, Two, Three` / `First, Second, Third`），不是普通正文字符串；超过 Word 可显示范围时仍按“已知缺陷与降级”处理。

### 已知缺陷与降级

以下标准枚举暂未有可靠的 Word 实物夹具和可确认的跨区域序列实现：`ideographTraditional`、`koreanLegal`、`koreanDigital2`、`hindiCounting`、`thaiCounting`、`vietnameseCounting` 及应用自定义值。解析器会保留段落和 `numFmt` 元数据，写入一次 `UNSUPPORTED_NUMBER_FORMAT` 警告，并将该占位值降级为十进制文本；不把它伪装成正确的本地化文本。

已实现的东亚文字计数格式超过 `999999` 时也会降级为十进制并报告 `NUMBERING_VALUE_OUT_OF_RANGE`。这不同于 Word 对若干格式直接留空的行为，是为了避免让段落消失；范围行为与 Word 的差异可见同一份 [MS-OI29500 17.18.59](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/ea3612c8-a099-46c3-99a9-93658a30cb01)。`japaneseDigitalTenThousand` 的 Word 上限是 `9999`，当前实现尚未单独截断，属于同一范围缺陷。

定义新项目符号时，直接写入 Unicode 的符号和颜色可完整还原。图片项目符号可还原为图片资产。为了遵守“字体不解析”的契约，符号字体名称不会读取或保存；当前仅按常见 Word 模板中的代码点转换 `F06C`（实心圆）、`F06E`（实心方块）和 `F075`（实心菱形）。其余私有区代码点无法在不保留字体的前提下可靠显示。这是有意保留的限制，必须以对应的真实文件和 golden 输出确认后再扩展映射。
