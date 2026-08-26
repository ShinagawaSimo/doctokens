# DOCX 解析输出格式说明

本文档面向下游开发者和 LLM tool description 编写者，解释 `docx-llm-parser` 输出的语义 HTML5 标记格式。

## 总体设计

解析器将 `.docx` 文件转化为三种密度的输出：

| 密度  | 枚举值                           | 文件                | 内容                               |
| --- | ----------------------------- | ----------------- | -------------------------------- |
| 语义级 | `SEMANTIC` (`"semantic"`)     | `parsed.html`     | 完整 HTML5 标记，含所有内联格式、对象引用和表格结构    |
| 结构级 | `STRUCTURAL` (`"structural"`) | `structural.html` | 块级结构 + 语义对象，去除粗体/斜体/颜色等视觉格式      |
| 纯文本 | `PLAIN` (`"plain"`)           | `plain.txt`       | 纯文本流，段落间以空行分隔；脚注拼接到段末，尾注与批注拼接在文末 |

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

本解析器通过 OOXML 中存储的，上一次在 Word 等软件中打开 docx 文档时渲染的分页位置记号，生成解析后的页码标记。

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

| 元素        | semantic                        | structural                     | plain                   |
| --------- | ------------------------------- | ------------------------------ | ----------------------- |
| 标题        | `<h1>`–`<h6>`                   | `<h1>`–`<h6>`                  | 退化为普通段落（`\n\n` 分隔）      |
| 段落        | `<p>` + `\n\n`                  | 同 semantic                     | 纯文本 `\n\n`              |
| 段落内换行     | `\n`                            | `\n`                           | `\n`                    |
| 粗体/斜体/颜色等 | `<b>` `<i>` `<color value=>` 等  | 全部去除                           | 无                       |
| 表格        | 完整 HTML 表格 + 合并单元格              | 完整 HTML 表格 + 合并单元格             | `\t` 分隔纯文本，>10 行截断      |
| 表格截断阈值    | 30 行                            | 30 行                           | 10 行                    |
| 图表        | `<chart>` + 属性 + `truncated`    | 同 semantic                     | `[Chart: ...]` 纯文本摘要    |
| SmartArt  | `<smartart>` + 属性 + 全部节点文本      | 同 semantic                     | `[SmartArt ...]` 纯文本摘要  |
| 图片        | `<img id=... alt=...>`          | `<img>` 占位                     | `[Image]`               |
| 嵌入对象      | `<embedded>` + type/name        | `<embedded>` + type/name       | 不输出                     |
| 文本框       | `<textbox alt=...>` + 文字        | 同 semantic                     | 文字直接融入正文流               |
| 公式        | `<equation>` 内容                 | `<equation>` 内容                | 文字直接融入正文流               |
| 脚注        | `<footnoteref/>` + supplemental | 同 semantic                     | 拼接到段末 `[fnN: content]`  |
| 尾注        | `<endnoteref/>` + supplemental  | 同 semantic                     | 拼接到文末 `[edN: content]`  |
| 页码        | `<page=N>`                      | `<page=N>`                     | 无                       |
| 页眉/页脚     | supplemental 区                  | 不输出                            | 不输出                     |
| 批注        | `<commentref/>` + supplemental  | `<commentref/>` + supplemental | 拼接到文末 `[cmtN: content]` |

## 资源提取 API

正文中被截断的资源（`<table truncated>`、`<chart ... truncated>`、`<smartart ... truncated>`）可通过 `get_resource` 按需获取完整数据：

### 单资源详情

| 调用                                                                                       | 返回                           |
| ---------------------------------------------------------------------------------------- | ---------------------------- |
| `get_resource(parsed, ResourceType.TABLE, "t1")`                                         | 完整表格（合并分页片段，含 rows 数组）       |
| `get_resource(parsed, ResourceType.TABLE, "t1", rows="10-25")`                           | 指定行范围（1-based，含起止行）          |
| `get_resource(parsed, ResourceType.TABLE, "t1", columns=["金额","日期"])`                    | 仅指定列（按表头名称匹配）                |
| `get_resource(parsed, ResourceType.TABLE, "t1", aggregate="sum", aggregate_column="金额")` | 聚合值。支持 sum/count/avg/min/max |
| `get_resource(parsed, ResourceType.CHART, "chart1")`                                     | 完整图表数据点（缓存数据）                |
| `get_resource(parsed, ResourceType.SMARTART, "smartart1")`                               | 完整节点和连接列表                    |
| `get_resource(parsed, ResourceType.IMAGE, "img1")`                                       | 图片 bytes（含 contentType）      |

`rows` 和 `columns` 可组合使用。`aggregate` 基于表格文本中的数值计算，不做公式重算。Chart 和 SmartArt 也可通过 structural/semantic 输出的 `get_resource` 入口获取完整数据，无需先读全文。

## 特殊约定

- 所有方括号标记（如 `[fn1]`、`[Image]`、`[Chart: ...]`）是 plain 专用的纯文本占位符，不出现在 structural/semantic 中
- `<br>` 标签已被 `\n` 替代，不在任何密度中出现
- 表格 id（`tableId`）在解析阶段分配，同篇文档多次解析结果一致
- 属性值含空格或特殊字符时使用双引号包裹并进行 HTML 转义

## 附1：列表编号

本项目支持 Word 中“项目符号”、“编号”和“多级列表”的文字流还原，编号文本会保留在段落内容中。semantic 密度下，段落起始处会额外保留 `numbering` 标记，帮助区分自动编号文本与正文内容。

“项目符号”的颜色、加粗和斜体会进入 semantic 输出。图片项目符号会在段首以 `<img>` 输出。

当前已对Microsoft Word 中的通用默认编号样式，以及系统环境语言为简体中文、日文时的新增默认编号样式进行了逐项验证，确认可精确还原 Word 中的自动编号行为特征。已验证的编号样式见下表：

| 编号样式枚举值                   | 规范名称          | 注释      |
| ------------------------- | ------------- | ------- |
| `aiueo`                   | AIUEO 顺序半角片假名 |         |
| `aiueoFullWidth`          | AIUEO 顺序全角片假名 |         |
| `bullet`                  | 项目符号          |         |
| `cardinalText`            | 基数词文本         |         |
| `chineseCountingThousand` | 中文计数千位系统      |         |
| `chineseLegalSimplified`  | 中文简体法律格式      | 即中文大写数字 |
| `decimal`                 | 十进制数字         |         |
| `decimalEnclosedCircle`   | 带圈十进制数字       |         |
| `decimalFullWidth`        | 全角阿拉伯数字       |         |
| `decimalZero`             | 前导零阿拉伯数字      |         |
| `ideographDigital`        | 表意数字          |         |
| `ideographTraditional`    | 传统表意格式        | 即天干编号   |
| `ideographZodiac`         | 生肖表意格式        | 即地支编号   |
| `iroha`                   | 伊吕波顺序片假名      |         |
| `irohaFullWidth`          | 全角伊吕波顺序片假名    |         |
| `japaneseCounting`        | 日语计数系统        |         |
| `japaneseLegal`           | 日语法律编号        | 即日文大写数字 |
| `lowerLetter`             | 小写拉丁字母        |         |
| `lowerRoman`              | 小写罗马数字        |         |
| `none`                    | 无编号           |         |
| `ordinal`                 | 序数词           |         |
| `ordinalText`             | 序数词文本         |         |
| `upperLetter`             | 大写拉丁字母        |         |
| `upperRoman`              | 大写罗马数字        |         |

其余的 ISO/IEC 29500 规范中所规定的标准编号格式均已支持显示转换，但尚未通过真实 Word 文件逐项验证其全部显示规则。

项目的编号解析严格按照 Microsoft Word 的实际渲染表现实现，当 Word 的实际行为与 ISO/IEC 29500 规范及 MS-OI29500 规范描述不一致时，以 Word 的实际表现为准。当前已根据真实 Word 文件确认的与规范间的差异包括：

* `aiueoFullWidth`在 Word 中，超过46项循环后回到第一项、始终以单字符编号，与 MS-OI29500 2.1.548 f. 描述的循环后增加一次字符重复次数不符。

* `chineseCountingThousand`在 Word 中，在万位后接不足一千的数值时显示`〇`（即10050→`一万〇五十`），与 MS-OI29500 2.1.548 e. 描述的中间不输出任何字（`一万五十`）及 ISO/IEC 29500 17.18.59 描述的中间输出`零`不符。
