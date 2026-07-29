# DOCX 底层解析工具 Python 开发文档

版本：v0.8  
日期：2026-07-30  
实现语言：Python 3  
当前状态：已完成输出格式切换（HTML5隐式闭合）、图片哈希命名、上下标支持。

## 1. 开发目标

本工具的目标不是复刻 Word 排版，而是把 `.docx` 中的可读内容转换成大模型可以稳定理解、引用和回答问题的语义 HTML5 标记。

实际用户可能会问：

- “帮我概括第 X 页的内容。”
- “总结第 X 页第 Y 段。”
- “表 2 讲了什么？”
- “图 3 附近的段落是什么意思？”
- “脚注 5 的依据是什么？”
- “这段文字有没有批注？”
- “这份文档里的超链接指向哪里？”
- “按最终修订文本总结全文。”

因此最终 XML 需要保留的不是所有解析字段，而是完成这些任务必要的信息：

- 正文顺序。
- 段落序号。
- 表格序号。
- Word 自动编号/项目符号的可见文本。
- 轻量页码线索。
- 标题层级，前提是 Word 样式明确给出。
- 表格行列文本。
- 图片/图形的引用、alt、文件路径。
- 脚注/尾注/批注引用及正文。
- 超链接目标。
- 字段指令的轻量提示。
- 修订文本策略。
- 文本框文字、公式文本等可能被用户直接提问的嵌入内容。

不应进入最终 XML 的内容：

- `part`
- `styleId`
- `runs`
- `rawHints`
- `relationshipId`
- `numId`
- `ilvl`
- `lvlText`
- `numFmt`
- `fontName`
- `fontSize`
- `themeColor`
- `contentTypes`
- package 内部路径
- 完整 relationships
- 完整 styles

这些只进入 debug 目录。

## 2. 已实现范围

当前实现覆盖：

1. 只支持 `.docx`。
2. ZIP / OPC / relationship 解析。
3. `word/document.xml` 段落和表格解析。
4. `word/styles.xml` 标题识别。
5. `word/numbering.xml` 自动编号：根据 `numId`、`ilvl`、`numFmt`、`lvlText` 计算“一．”“二．”“A.” 等可见段落标记，并插入最终文本流。
6. 轻量文字格式：解析粗体、斜体、下划线、删除线、字体颜色、高亮和背景色，最终 XML 用少量语义标签表达。
7. 图片和媒体资源：解析 image relationships，导出嵌入图片到 `assets/`，正文中输出 `<image ref="..."/>`。
8. 页眉页脚、脚注尾注、批注：解析为 supplemental XML。
9. 字段和超链接：超链接输出 `<link>`，字段指令输出轻量 `<field>`。
10. 修订模式：支持 `final`、`original`、`review` 三种策略。
11. 关系索引：把 OPC relationships 建成只读索引，正文、图片、后续 chart/textbox/OLE 解析都通过索引读取。
12. 文档级并发 API：`parse_many()` 以单篇文档为并发单位，保持单篇内部顺序解析。
13. 共享 inline 解析：正文、页眉页脚、脚注尾注和批注复用同一个 `InlineParser`，避免链接、格式、对象引用在不同 part 中解析能力不一致。
14. 文本框：支持 DrawingML/WPS 和旧式 VML `w:txbxContent`，最终 XML 输出 `<textbox>`，只保留文字、placement 和 alt/title；自动生成的 shape name 只进 debug。
15. 公式：支持 OMML `m:oMath` / `m:oMathPara` 的轻量文本抽取，最终 XML 输出 `<eq>`。
16. 复杂表格增强：顶层表输出 `rows/cols`，纵向合并起点补充 `rowspan`，嵌套表格输出 `<nested-table>`，不再只留在 debug。
17. 性能观测：debug 输出 `metrics.json`，记录 ZIP、relationship、styles、numbering、assets、embedded_objects、body、ancillary、debug 写入、render/write 等阶段耗时和输出规模；XML 写出阶段改为流式迭代写入。
18. 样式热路径优化：`StyleMap` 对 heading level、numbering、run format 解析做只读缓存，避免大文档中重复递归样式继承链。
19. 图表轻量解析：解析实际 relationship 指向的 `word/charts/chart*.xml`，最终 XML 输出 `<chart>`，包含图表类型、标题、系列数、点数、系列名、min/max 和少量缓存点 preview。
20. SmartArt 轻量解析：解析实际 relationship 指向的 `word/diagrams/data*.xml`，最终 XML 输出 `<smartart>`，包含节点文本和节点间连接关系。

### 2.1 性能优化（v0.7，2026-07-29）

21. **预计算标签名**：`core/constants.py` 新增 50+ 个常用 `qn()` 标签的模块级常量（`_TAG_W_P`、`_TAG_W_RPR` 等），避免热路径中每次 `qn(prefix, local)` 做 `f"{{{ns}}}{local}"` 字符串拼接。

22. **单次遍历子节点**：`extractors/inline.py:_parse_run()` 原来先 `first_child(run, "rPr")` 扫描一遍子节点，再 `for child in run` 扫描第二遍。现在合并为一次迭代，子节点标签用预计算常量直接比对（`child_tag == _TAG_W_RPR`）。

23. **local_name_fast**：新增 `local_name_fast(tag)`，用 `rfind("}")` + 切片替代 `rsplit("}", 1)[1]`，避免 split 产生的 list 内存分配。body iterparse 循环中每次 event 调用此函数，每秒数千次。

24. **异步 debug 写入**：`core/debug.py:DebugWriter` 新增 `enable_async()`/`wait_all()` 模式。debug JSON 序列化和磁盘 I/O 提交到 `ThreadPoolExecutor(max_workers=1)` 后台线程。debug_write 阶段从 218ms 降至 2ms（异步提交耗时）。

25. **dataclass __slots__**：`StyleRecord`、`RelationshipRecord`、`ParseWarning` 使用 `@dataclass(slots=True)`（Python 3.10+），减少每个实例的 `__dict__` 内存分配。

26. **lxml 方案实验（已放弃）**：在 `perf/lxml-optimization` 分支上尝试用 lxml.etree 替换 stdlib ElementTree，并使用预编译 `etree.XPath()` 加速深层 XML 查找。结果：大文档（4.5MB）body 解析 295→349ms（+18%），总耗时 392→455ms（+16%）。原因：CPython 3.12 的 stdlib ElementTree 底层已是 C 实现，对简单 iterparse/find 操作足够快；lxml 的 C 扩展调用反而引入额外开销。保留分支作为实验记录。

27. **输出格式切换为 HTML5（v0.8）**：废弃 XML 渲染器（`renderers/xml.py`），切换为 HTML5 隐式闭合格式（`renderers/html5.py`）。块级元素（`<p>`、`<h1>`~`<h6>`、`<tr>`、`<th>`、`<td>`）利用 HTML5 标准隐式闭合规则，遇到下一个块元素自动关闭。inline 元素（`<a>`、`<b>`、`<i>` 等）保留闭合标签。实测大文档 token 节省 31%（275KB→190KB）。提取 `_text_utils.py` 和 `_metrics.py` 共享模块消除渲染器间重复。

28. **图片内容哈希命名（v0.8）**：`extractors/assets.py` 中图片文件命名从 `img1.png` 改为 `img1_{sha256[:8]}.png`，防跨文档文件名冲突。下游工具通过 `img{序号}` 定位文件。资产元数据精简为仅保留 id、file、contentType。

29. **上下标支持（v0.8）**：`ooxml/formatting.py` 新增 `_read_vert_align()` 解析 `w:vertAlign` 元素。渲染器输出 `<sup>`/`<sub>` 标签。实测大文档输出 181 处 `<sup>`、32 处 `<sub>`。

**性能基线（4.5MB docx，debug=False）：**

| 指标 | v0.6 (优化前) | v0.7 (优化后) | 变化 |
|---|---|---|---|
| body 解析 | 307ms | 295ms | -4% |
| 总耗时 | 404ms | 392ms | -3% |
| debug_write | 218ms | 2ms (异步) | -99% |

仍未实现或只做轻量记录：

- 图表 embedded workbook 完整数据。
- 图表高保真样式和渲染外观。
- SmartArt 精确图形布局和形状样式。
- 文本框精确位置和形状样式。
- OMML 到 MathML/LaTeX 的高保真转换。
- OLE 嵌入对象。
- 真实页码渲染对齐。
- PDF 坐标级定位。

## 3. 技术路线

本工具不依赖 `python-docx`、docx4j、Apache POI、Open XML SDK 等项目库，底层优先使用 Python 标准库：

```text
zipfile
xml.etree.ElementTree
dataclasses
argparse
pathlib
html.escape
```

实现思路借鉴成熟库：

| 项目 | 借鉴点 |
|---|---|
| Open XML SDK | Part、Relationship、Content Type 是一等概念；大文件用 OpenXmlReader/SAX 式前向读取思路 |
| Apache POI XWPF | 正文按 body elements 顺序输出，段落和表格都是 block，不按类型分两遍读取 |
| docx4j | 先建立 package/part/relationship 图，再进入正文和资源解析 |
| python-docx | 上层暴露简单对象，底层仍保留 XML 线索；正文段落/表格按出现顺序迭代 |

当前工程结构：

```text
docx_llm_parser/
  core/        # 数据模型、ZIP/OPC、XML 小工具、debug 写入
    relationships.py  # OPC relationship 只读索引
  ooxml/       # styles、numbering、formatting 等 OOXML 定义解析
  extractors/  # document.xml、assets、inline、headers/notes/comments 等内容抽取
    inline.py  # 段落内 run、链接、格式、图片、文本框、公式等共享解析逻辑
  renderers/   # 面向大模型的最终 XML 渲染
  concurrency.py # 文档级并发解析 API
  parser.py    # 解析流程编排入口
```

## 3.1 信任边界与内部契约

后续开发遵守这个原则：不要为理论上不可能缺失的内部字段写默认值兜底。

需要保留的边界处理：

- ZIP entry 数量、解压大小、路径穿越校验。
- 可选 part 缺失，例如 `styles.xml`、`numbering.xml`、`footnotes.xml`。
- 外链资源不下载。
- debug 写入失败只记录 warning。
- 当前尚未支持的合法 OOXML 节点记录 warning。

不应继续编写的无效防御：

- `block["type"]`、`block["page"]`、`table["rows"]`、`cell["text"]` 这类内部结构字段不写 `get(..., 默认值)`。
- `relationship` 的 `Id`、`Type`、`Target` 和 Content Types 的必需属性按规范直接读取。
- 主流程已经创建的 `RelationshipIndex`、`NumberingState`、`asset_lookup` 不在下游重复判断是否存在。

这样做的好处是：坏的内部流转会在开发阶段尽早暴露，而不是被空字符串、空列表吞掉，最后生成一份看似合法但语义缺失的 XML。

## 4. 输出策略

### 4.1 最终输出

最终只输出：

```text
out/<docx_stem>/parsed.html
```

HTML5 隐式闭合结构（块级元素无需 `</p>`、`</h2>`、`</td>` 等闭合标签）：

```html
<!-- source="sample.docx" -->

<p i=b1 g=1>第一段正文。
<p i=b2 g=1>带<a h=https://example.com>链接</a>的段落。
<h2 i=b3 g=1>二．摄影拼接
<p i=b4 g=1><b>粗体段落</b>，以及<c v=#FF0000>红色文字</c>。
<p i=b5 g=1>图形中的文字：<tb alt=说明>文本框内容</tb>
<p i=b6 g=1>公式：<eq>x+1=y</eq>
<p i=b7 g=1><chart i=c1 k=bar t=人口趋势 s=1 p=2><s n=人群A p=2 min=1.5 max=2.5 pv=一期=1.5; 二期=2.5/></chart>
<p i=b8 g=1><sa i=s1 n=2 l=1><n i=1>采集</n><n i=2>分析</n><e f=1 t=2 k=parOf/></sa>
<table i=b9 g=1>
<tr h>
<th>姓名
<th>角色
<tr>
<td>张三
<td>作者<ntable r=1 c=1><r><td>嵌套信息

<!-- assets -->
<img i=img1 f=assets/img1_a3f2b9c1.png m=image/png>

<!-- supplemental -->
<fn id=1>脚注正文。
<cm id=2 a=Alice>批注正文。
```

格式要点：
- 块级元素隐式闭合（HTML5 标准行为），新块开始 = 前一个块结束
- 单字符属性名省 token：`i`=id, `g`=page, `h`=href, `v`=value, `s`=size/span, `f`=file, `m`=MIME type
- inline 元素仍需闭合（`<a>...</a>`、`<b>...</b>` 等），因为格式化范围必须标记边界
- 图片文件以内容哈希命名（`img1_a3f2b9c1.png`），防跨文档冲突
- 实测 4.5MB docx：XML 275KB → HTML5 190KB（-31% token）

### 4.2 为什么保留 `id` 和 `page`

这些不是解析噪声，而是用户任务需要的定位信息：

- `id`：最终 XML 中正文块的唯一定位符，同时承担原先块级 `n` 的顺序定位功能。比如 `<p id="b23">` 表示 `<body>` 下第 23 个可见 block，后续工具调用、高亮、引用都使用它。
- `page`：回答“第 X 页”相关问题的线索。

块级元素不再输出单独的 `n`，因为它和 `id` 表达的是同一套全局顺序。最终 XML 的 `id` 在输出阶段按可见 body block 连续生成，不复用 debug 中的内部解析 ID。这样可以减少最终 XML 的字段数量，避免大模型把 `id`、`n` 理解成两种不同定位体系。表格内部的 `<row n="...">` 和 `<cell c="...">` 仍然保留，因为它们表示表格行列坐标，不属于块级重复字段。

注意：`page` 不是 Word 真实渲染页码，只是基于 OOXML 中手动分页符和 `lastRenderedPageBreak` 的 page hint。文档中标记为 `pageModel="ooxml-hints"`，避免误导。

### 4.3 轻量文字格式

最终 XML 只输出模型完成阅读任务需要的可见格式，不输出字体名、字号、主题色来源、样式 ID 等解析字段。

| Word 可见格式 | 最终 XML |
|---|---|
| 粗体 | `<b>文本</b>` |
| 斜体 | `<i>文本</i>` |
| 下划线 | `<u>文本</u>` |
| 删除线 | `<s>文本</s>` |
| 字体颜色 | `<color value="#FF0000">文本</color>` |
| 文本高亮 | `<mark color="yellow">文本</mark>` |
| 底纹背景 | `<bg color="#00FF00">文本</bg>` |

轻量化规则：

- 相邻且输出语义相同的 run 会在渲染阶段合并。
- 接近默认黑色的字体颜色不输出。
- 超链接默认蓝色/下划线不重复输出，因为 `<link>` 已经表达了链接语义。
- 格式来源、直接格式、字符样式、段落样式继承链等细节只进入 debug。

## 5. Debug 输出

debug 常开，默认目录：

```text
out/<docx_stem>/debug/
```

输出：

| 文件 | 内容 |
|---|---|
| `zip_index.json` | ZIP entry 索引 |
| `content_types.json` | Content Types |
| `relationships.json` | 全部 relationships |
| `styles.json` | 样式摘要 |
| `numbering.json` | 自动编号定义 |
| `internal_blocks.json` | 内部完整 block |
| `assets.json` | 图片资源清单 |
| `embedded_objects.json` | 图表和 SmartArt 轻量对象清单 |
| `ancillary.json` | 页眉页脚、脚注尾注、批注 |
| `body_events.jsonl` | body block 事件流 |
| `warnings.json` | warning 列表 |
| `summary.json` | 统计摘要 |
| `metrics.json` | 阶段耗时、节点计数、输出大小、估算 token |

debug 原则：

- 可以包含解析字段。
- 不作为 LLM 最终输入。
- 不输出图片二进制。
- debug 写入失败只记录 warning，不影响主解析。
- 当前开发阶段 debug 默认常开，便于回归和审查；调研文档里“批量/线上默认关闭”的建议只适合后续的 wrapper 层，不适合作为当前开发基线。
- 后续可补 `debug_level`、`debug_max_bytes_per_file`、`debug_sample_blocks`，但不把 debug 从 parser 核心里拿掉。

## 6. 标题识别规则

标题只按正常 OOXML 样式流程识别：

1. 段落样式在 `styles.xml` 中明确存在 `w:outlineLvl`。
2. 段落样式继承链上明确存在 `w:outlineLvl`。

不做任何 fallback：

- 不根据 `Heading1`、`标题 1` 等样式名猜测。
- 不根据段落文本形态猜测。
- 不根据字号、加粗、短行猜测。

原因：大模型可以直接读取普通段落，错误的标题识别会污染文档结构。

## 7. Word 自动编号

Word 的自动编号通常不存放在 `w:t` 文本中，而是由两部分共同决定：

- 段落属性：`w:pPr/w:numPr/w:numId` 和 `w:ilvl`。
- 编号定义：`word/numbering.xml` 中的 `w:num`、`w:abstractNum`、`w:lvl`、`w:numFmt`、`w:lvlText`、`w:start`。

解析策略：

1. 先解析 `numbering.xml`，建立 `numId -> abstractNum -> level` 的只读索引。
2. 正文流式解析时，每遇到带编号的段落，就用独立的 `NumberingState` 推进该 `numId/ilvl` 的计数。
3. 把计算出的可见编号作为合成 run 插入段落开头，例如 `二．	摄影拼接`、`A.	管理/控制`。
4. 如果段落本身没有 `numPr`，但样式继承链上明确存在 `numPr`，也按样式编号处理。
5. `numId`、`ilvl`、`lvlText`、`numFmt` 等解析字段只进入 debug，不进入最终 XML 属性。

这不是启发式：解析器不根据“一、”“二、”“A.”等文本形态猜编号，只使用 OOXML 明确给出的编号结构。最终 XML 直接包含编号文本，是因为它属于 Word 中用户实际可见的正文内容。

当前支持的常见编号格式：

- `decimal`、`decimalZero`
- `upperLetter`、`lowerLetter`
- `upperRoman`、`lowerRoman`
- `chineseCounting`、`japaneseCounting`、`taiwaneseCounting`
- `bullet`

未覆盖的 `numFmt` 会在 debug warning 中记录，并暂时用十进制兜底，避免整篇文档解析失败。

## 8. 页码策略

纯 OOXML 不能可靠计算真实页码。当前只提供 page hint：

- 遇到 `w:br w:type="page"` 后，后续 block 页码递增。
- 遇到 `w:lastRenderedPageBreak` 后，后续 block 页码递增。

这个策略可以支持初步回答“第 X 页附近内容”，但不能保证与 Word/WPS/LibreOffice 当前渲染页码一致。

如果用户需要精确页码，后续必须增加：

```text
DOCX -> PDF/PNG 渲染
PDF 文本坐标抽取
XML block 与 PDF 页面近似对齐
```

## 9. 修订策略

CLI 参数：

```text
--revision-mode final
--revision-mode original
--revision-mode review
```

语义：

| 模式 | 行为 |
|---|---|
| `final` | 插入文本保留，删除文本跳过 |
| `original` | 插入文本跳过，删除文本保留 |
| `review` | 插入文本包为 `<ins>`，删除文本包为 `<del>` |

默认是 `final`，适合大多数总结、问答、RAG 场景。

## 10. 图片与媒体资源

当前实现：

- 扫描 image relationships。
- 嵌入图片复制到 `out/<docx_stem>/assets/`。
- 正文中的 `w:drawing` 尝试解析 `a:blip/@r:embed`。
- 最终 XML 使用 `<image ref="img1" file="assets/img1.png" placement="inline" />` 引用。
- DrawingML/WPS 和 VML 文本框读取 `w:txbxContent`，最终 XML 输出 `<textbox>`。

对大模型有用的信息：

- 图片出现位置附近的段落。
- 图片 alt/title/name。
- 图片文件路径。
- inline/anchor placement。
- 文本框中的可见文字。

文本框目前只抽取可见文字和少量辅助信息，不尝试还原形状尺寸、层叠位置、环绕方式和内部段落格式。原因是当前目标是让 LLM 能回答“文本框里写了什么”“这段附近有没有图形文字”，而不是复刻 Word 绘图层排版。

图片内容识别暂不属于 OOXML 解析范围，后续可接 OCR 或视觉模型。

### 10.1 图表

当前实现读取正文或 supplemental 实际引用到的 chart relationship，并解析 `word/charts/chart*.xml` 中的缓存信息。最终 XML 输出 `<chart>`，只保留：

- chart id。
- 图表类型，例如 bar、line、pie、scatter。
- 标题。
- 系列数量和点数量。
- 系列名。
- 每个系列的 min/max。
- 每个系列前若干个缓存点 preview。

不读取 embedded workbook 的完整 Excel，不做图表渲染，也不输出坐标轴样式、颜色、数据标签位置、三维视角等图形层信息。原因是用户常见问题通常是“这个图表说明什么趋势”“横纵轴是什么”“有哪些系列”，这些可以由 chart XML 缓存和上下文段落回答；完整工作簿和图形样式会显著增加解析成本和 token。

### 10.2 SmartArt

当前实现读取实际引用到的 SmartArt data relationship，并解析 `word/diagrams/data*.xml`。最终 XML 输出 `<smartart>`，只保留：

- smartart id。
- 节点数量和连接数量。
- 节点文本。
- 节点之间的轻量连接关系。

不保留精确坐标、环绕、层叠、箭头路径、填充色、阴影、旋转等图形层信息。对常见 LLM 任务来说，节点文本和关系足以回答“流程图有哪些步骤”“组织结构图有哪些层级”“关系图表达了什么”。

## 11. 脚注、尾注、批注

当前实现：

- `word/footnotes.xml` -> `<footnotes><note id="...">...`
- `word/endnotes.xml` -> `<endnotes><note id="...">...`
- `word/comments.xml` -> `<comments><comment id="..." author="...">...`
- 正文中的 `footnoteReference`、`endnoteReference`、`commentReference` 输出轻量引用。
- 页眉页脚、脚注尾注和批注正文复用 `InlineParser`，因此其中的链接、文字格式、图片引用、文本框和公式也会进入 supplemental XML。

这样用户问“脚注 5 是什么”“这段有没有批注”时，大模型至少能通过 XML 关联理解。

## 12. 字段和超链接

当前实现：

- `w:hyperlink` 中的显示文本保留为 `<link href="...">文本</link>`。
- `w:instrText` 记录为 `<field instruction="..."/>`。

字段缓存是否最新不做承诺。目录、页码、交叉引用的准确性后续需要字段更新或渲染引擎辅助。

### 12.1 公式

当前实现读取 `m:oMath` 和 `m:oMathPara`，把其中显式保存的公式文本压缩为 `<eq>...</eq>`。这一步不做启发式公式识别，也不把 OMML 全量结构塞进最终 XML。这样处理的理由是：初版 LLM 任务通常需要知道“这里有公式、公式大致是什么”，而不是立即恢复每一个数学排版节点。

后续如果用户需要“把所有公式转 LaTeX”“比较公式编号”“检查上下标结构”等任务，需要新增 OMML 到 MathML/LaTeX 的专门转换层，并把转换失败记录到 debug warning。

## 13. 并发与速度

并发单位仍然建议是文档级：

```text
worker-1 parse a.docx
worker-2 parse b.docx
worker-3 parse c.docx
```

单文档内部保持顺序解析，因为正文 block 顺序对用户定位任务非常重要。

当前 API：

```python
from docx_llm_parser import parse_many

results = parse_many(["a.docx", "b.docx"], "out", max_workers=4)
```

`parse_many()` 的返回结果与输入顺序一致。每个 worker 使用独立的 `DocxParser`、`ParseOptions`、`DebugWriter`、`NumberingState` 和输出目录，因此没有全局可变状态。

性能策略：

- ZIP entry 按需读取。
- `document.xml` 使用 `iterparse()` 流式读取。
- relationships 先构建只读索引，后续按 `(sourcePart, rId)` 或 relationship type 直接查询。
- 正文和 supplemental 共享 `InlineParser`，避免每个 part 复制一套 run 解析逻辑，也避免热路径上重复实现格式、链接和对象判断。
- `StyleMap` 缓存样式继承解析结果，避免大量 run 重复递归 `basedOn` 链。
- 图片按流复制，不放进 XML。
- 最终 XML 写文件采用迭代式片段输出，避免大文档额外构造完整 XML 字符串。
- debug 与最终 XML 分离。
- 单文档没有全局可变状态，便于并发。
- 对更大文档或更重的正文路径，后续可按 preflight 结果把 worker 切到 process pool；当前 `parse_many()` 先提供文档级并发入口，资源预算调度和软/硬超时会放到下一轮。

当前大文档计时样本：

```text
文件：广西新石器时代中期贝丘遗址人群生存策略、人口与健康研究.docx
输入大小：4,768,433 bytes
ZIP 解压总量：6,754,462 bytes
输出 XML：275,039 bytes / 约 48,838 tokens
端到端 CLI 耗时：约 1.08s
parser metrics totalMs：约 627ms
body：约 307ms
debug_write：约 198ms
assets：约 43ms
render_write：约 37ms
warningCount：1
```

结论：在 debug 常开的开发模式下，这类 4.7MB、27 个图片资源、153 条尾注、13 个表格的文档可以在约 1 秒内完成 CLI 解析和写出。当前主要成本不是 ZIP 预检或 relationship，而是正文 XML 遍历、debug 大 JSON 写入和图片复制。下一轮性能优化应优先考虑 debug 分级/采样、表格与 supplemental 的预算输出、locator/window 视图，而不是急于把单文档内部拆成并发解析。

## 14. CLI

执行：

```powershell
python docx_parser_cli.py "第6章.docx" --out out
```

可选：

```powershell
python docx_parser_cli.py "第6章.docx" --out out --revision-mode review
```

当前不会生成 Markdown。

## 15. 验收标准

执行后应生成：

```text
out/第6章/parsed.xml
out/第6章/debug/zip_index.json
out/第6章/debug/content_types.json
out/第6章/debug/relationships.json
out/第6章/debug/styles.json
out/第6章/debug/numbering.json
out/第6章/debug/internal_blocks.json
out/第6章/debug/assets.json
out/第6章/debug/embedded_objects.json
out/第6章/debug/ancillary.json
out/第6章/debug/body_events.jsonl
out/第6章/debug/warnings.json
out/第6章/debug/summary.json
out/第6章/debug/metrics.json
```

检查点：

- `parsed.xml` 是合法 XML。
- `<body>` 下 block 顺序正确。
- 块级元素有 `id` 和 `page`，不再输出重复的块级 `n`。
- Word 自动编号进入最终文本，例如 `二．	摄影拼接`、`A.	管理/控制`。
- 粗体、颜色等可见文字格式用轻量标签进入最终 XML。
- 表格保留行列。
- 图片资源不内嵌二进制。
- 文本框以 `<textbox>` 输出可见文字。
- OMML 公式以 `<eq>` 输出轻量文本。
- 图表以 `<chart>` 输出类型、标题、系列和缓存点摘要。
- SmartArt 以 `<smartart>` 输出节点文本和连接关系。
- 嵌套表格以 `<nested-table>` 输出轻量结构。
- 页眉页脚、脚注尾注、批注中的链接和格式不会被降级成纯文本。
- debug 文件齐全。
- `metrics.json` 包含阶段耗时、输出大小和节点计数。
- 旧的 `readable.md` 不再生成。

最小回归测试：

```powershell
python -m unittest discover -s tests
```

当前测试覆盖 OMML 公式、DrawingML/VML 文本框、图表缓存摘要、SmartArt 节点关系、嵌套表格 XML 和 `vMerge` 推导 `rowspan`。

## 16. 后续开发

下一步建议：

1. 视图分层：增加 `manifest/outline/window/full`，让大模型默认先拿低 token 的结构索引，需要精读时再取局部 XML。
2. debug 分级和预算：在 debug 常开的前提下增加 `summary/full` 级别，避免大文档每次都写完整 `internal_blocks.json`。
3. 表格预算：大表格默认输出表头、尺寸、样例行和 locator，小表仍完整输出。
4. 图表增强：在 chart cache 不足时按需读取 embedded workbook 摘要，但仍不输出完整工作簿。
5. SmartArt 增强：补充 layout part 的轻量布局名称，但不进入图形层高保真。
6. OMML 高保真转换：OMML 转 MathML 或 LaTeX，并保留转换失败 warning。
7. 图片 OCR：对 assets 中图片做文字识别。
8. 精确页码：渲染 PDF 后做 XML block 对齐。

### 16.1 当前图表解析范围

用户关于图表的常见任务通常是：

- “图 3 说明了什么趋势？”
- “这篇文档有哪些图表？”
- “某个柱状图/折线图的横轴和纵轴是什么？”
- “表格和图表的数据是否一致？”

因此当前图表解析只保留最基本、最有问答价值的信息：

- 图表出现位置：作为段落 inline object 输出 `<chart>`。
- 图表类型：bar、line、pie、scatter、area 等。
- 标题和图例文字。
- 系列数量、系列名。
- 分类轴标签和数值缓存的轻量摘要。
- 点数量、最大/最小值、前若干个点的 preview。
- 如果 chart XML 缺少缓存数据，输出 chart placeholder 和 relationship/debug warning。

当前不读取 embedded workbook 的完整 Excel，不做图表渲染，不复刻坐标轴样式、颜色、数据标签位置、三维视角和图形层布局。这样做的原因是：大模型通常需要理解“图表表达的内容”，不是检查某个柱子的像素位置。缓存数据足够时，直接读 `chart*.xml` 比打开 embedded workbook 更快、更稳定，也更符合当前“及时返回有效文本”的目标。

### 16.2 当前 SmartArt 解析范围

用户关于 SmartArt 的常见任务通常是：

- “这个流程图表达了哪几个步骤？”
- “组织结构图里有哪些层级？”
- “图里的几个概念是什么关系？”
- “请概括这张关系图。”

因此当前 SmartArt 解析只保留：

- SmartArt 出现位置：作为段落 inline object 输出 `<smartart>`。
- 布局类型或布局 part 的轻量名称。
- 节点文本列表。
- 节点间连接关系，如 parent-child、sequence、association。
- 节点数量和连接数量。
- 过大时只输出 preview 和 locator。

当前不做“图形层增强”：不保存形状精确坐标、环绕方式、层叠顺序、箭头路径、填充色、阴影、旋转、对齐参考线等。这些信息对常见 LLM 文档问答价值很低，却会显著增加 token 和解析复杂度。若用户真的提出“某段环绕的文本框内容”这类刁钻问题，模型可以结合对象所在段落上下文做近似判断；解析器不需要为这类低频任务把 DrawingML 全量结构塞进最终 XML。

## 17. 调研文档阅读报告

下面按研究文档中的具体结论逐条判断，不再按章节号做笼统汇总。每一条都写清楚四件事：原始结论、是否接纳、接纳原因、具体落实细节。

### 17.1 解析器核心和平台外壳必须分离
**原始结论：** `tfile_*`、直链下载、receipt、内容仓库、tool cache 都属于平台壳，不应进入 parser core。

**是否接纳：** 接纳。

**接纳原因：** 我们要的是一个干净的 `DOCX -> XML` 解析器，不是文件治理平台。只要把下载、TTL、内容仓库和缓存混进核心，解析器就会重新变成一层厚包装。

**具体落实细节：** 当前 parser 只接受本地可读的 `.docx` 路径、bytes 或 file-like object；不引入下载、TTL、receipt、content store、工具缓存。文档里继续把 `preflight / parse / render` 作为 parser 的唯一职责。

### 17.2 解析核心应该保持同步，异步只做外层包装
**原始结论：** `DoclingParser.parse()` 虽然是 `async`，但内部同步调用 `DocumentConverter.convert()`，会阻塞事件循环。

**是否接纳：** 接纳。

**接纳原因：** Word 解析本身就是同步的结构化 XML 流处理，把核心写成 async 只会让控制流更绕，真正的并发应该由调度层负责。

**具体落实细节：** 当前 `DocxParser.parse()` 保持同步；如果后续加异步入口，也只是在外层通过 executor 包装同步解析，不把 async 逻辑塞进正文解析核心。

### 17.3 输入预检必须覆盖 ZIP、XML part 和媒体资源
**原始结论：** DOCX 不能只看文件大小，还要看 ZIP entry 数量、单 entry 解压大小、总解压大小、压缩比、重复 entry、加密 entry、content type 和安全 XML 解析。

**是否接纳：** 接纳。

**接纳原因：** 这类风险不是“文档内容复杂”，而是“输入可能不适合进入解析核心”。越早失败，越省 CPU、内存和调试时间。

**具体落实细节：** `PackageReader` 继续承担 ZIP 安全预检，但后续文档要把 `max_input_file_bytes`、`max_compression_ratio`、`max_xml_total_uncompressed_bytes`、`max_media_total_uncompressed_bytes`、重复 entry、加密 entry、压缩方法白名单和 `safe_parse_xml_part()` 明确写成输入契约。

### 17.4 并发要文档级隔离，worker 选择要看资源预算
**原始结论：** 批量解析应该保留 semaphore 和单项失败隔离，但 worker 数不能只看 CPU，还要看文档大小、图片量、表格量和内存预算。

**是否接纳：** 接纳。

**接纳原因：** `ThreadPoolExecutor` 不是万能提速器，尤其是遇到大 XML、大表格和大量字符串拼接时，GIL 和内存峰值都会影响吞吐。

**具体落实细节：** `parse_many()` 继续作为文档级并发入口，但后续要补预算驱动的 worker 策略、有界提交和按文档大小选择 thread pool / process pool 的能力。单文档内部仍保持顺序解析，不能为了并发破坏 block 顺序。

### 17.5 版本化和可复现性必须成为输出契约
**原始结论：** parser 输出要带 `parser_version`、`schema_version`、`options_hash`，最好再加 `input_fingerprint` 和依赖版本。

**是否接纳：** 接纳。

**接纳原因：** 如果输出不带版本信息，上层就没法判断旧 XML 是否还能被新提示词、新 reader 或新 schema 正确理解，也没法做稳定缓存。

**具体落实细节：** 当前 `ParsedDocument.metadata` 已有基本字段，后续要继续补输入指纹、选项 hash 和依赖版本；缓存仍由上层负责，parser 只负责把结果写得可追踪、可比较、可失效。

### 17.6 最终输出应该分层，而不是只给一份完整 XML
**原始结论：** 省 token 的正解是 `manifest / outline / window / full` 四种视图，而不是单一一坨全文。

**是否接纳：** 接纳。

**接纳原因：** 不同任务要的信息不同。概括全文、找某页段落、查看某个表格、追踪脚注，这些根本不该拿同样大小的 XML 去回答。

**具体落实细节：** 当前 `parsed.xml` 先视为 `full` 视图；后续 renderer 要补 `manifest`、`outline` 和 `window`。`page` 只保留为 hint，不冒充真实排版页码，避免误导模型。

### 17.7 稳定 locator 比单一 id 更重要
**原始结论：** `internalId`、`xmlId`、`locator` 应该拆开，不要让 debug、最终 XML 和定位信息混成一层。

**是否接纳：** 接纳。

**接纳原因：** 现在一个 `id` 只能勉强定位 body 顺序，远远不足以支撑 window 回读、调试对齐和跨视图映射。

**具体落实细节：** 后续要明确三元组：解析器内部稳定 id、当前 XML 视图中的 id、以及可回到原文位置的 locator。当前实现先继续用顺序 id，但文档必须把这视为过渡方案。

### 17.8 结构化中间模型要先建树，再渲染 XML
**原始结论：** 不要边解析边拼字符串，应该先构建结构化中间文档，再序列化成目标 XML。

**是否接纳：** 接纳。

**接纳原因：** 只有先有中间模型，才谈得上不同视图、局部窗口、调试回放和后续 selector。直接拼字符串会把所有能力绑死在一种输出上。

**具体落实细节：** 当前 `ParsedDocument`、`blocks`、`assets`、`supplemental` 这套结构就是中间模型的骨架；extractor 负责生成结构，renderer 只负责序列化，不在 extractor 阶段提前拍扁成最终 XML。

### 17.9 正文顺序、标题和编号都要依赖显式 OOXML 结构
**原始结论：** 段落顺序要按 body 的原始顺序线性遍历；标题只能靠 `outlineLvl` 和样式继承链判断；自动编号要把 Word 可见编号恢复到正文里，不能靠文本形态猜。

**是否接纳：** 接纳。

**接纳原因：** 大模型可以直接读普通段落，错误的标题猜测会污染结构；而“一、二、A、B”这类编号本来就是用户可见文本，应该显式进入最终输出。

**具体落实细节：** 当前 body 继续用 `iterparse()` 保持顺序；标题识别继续只依赖样式链，不做文本启发式 fallback；自动编号保持前插到正文文本里，`numId`、`ilvl`、`lvlText`、`numFmt` 继续只进 debug。

### 17.10 表格和嵌套结构必须有轻量、摘要和完整三层表达
**原始结论：** 表格不能只当成二维字符串，复杂表格和嵌套表格需要区分轻量、摘要和完整表达。

**是否接纳：** 接纳。

**接纳原因：** LLM 常问的是“这张表讲什么”“第几页的那一列是什么”，不是一定要把整张大表原样塞进去。对大表格，token 和内存都比“还原率”更敏感。

**具体落实细节：** 现有实现保留行列、合并和嵌套 block；本轮已补充顶层表 `rows/cols`、纵向合并起点 `rowspan` 和最终 XML 中的 `<nested-table>`。后续要再加表格预算和视图分层：小表完整输出，大表只输出索引和摘要，特别大的嵌套表格需要提供可回读 locator，而不是无限内联展开。

### 17.11 图片和媒体应该引用化、去重和预算化
**原始结论：** 图片不能把二进制直接塞进 XML，应该输出引用、资源路径、alt/title/name，并控制资产规模。

**是否接纳：** 接纳。

**接纳原因：** 对 LLM 有用的是图片出现的位置、可读辅助信息和资源引用，不是把二进制混进文本流。这样既省 token，也方便后续 OCR 或视觉模型接手。

**具体落实细节：** 当前已经用 `assets/` 引用图片；后续要补去重 hash、资产预算、原子写入和 locator。最终 XML 里只保留可理解的引用字段，不把资源内容内联进正文。

### 17.12 supplemental 内容不能只剩纯文本
**原始结论：** 页眉页脚、脚注尾注、批注都应该分层处理，且最好复用正文的 inline 解析能力，而不是只抽纯文本。

**是否接纳：** 接纳。

**接纳原因：** 这些内容常常恰好是用户问到的地方。只保留纯文本会丢链接、格式和部分对象引用，和“尽可能保留可用信息”的目标冲突。

**具体落实细节：** 当前 `supplemental` 继续保留；本轮已让 `AncillaryParser` 复用正文 `InlineParser`，header/footer/footnote/endnote/comment 中的链接、格式、图片引用、文本框和公式会保留到 supplemental XML。尚未完成的是 section-aware 映射：页眉页脚目前按 part 输出，还没有根据 `sectPr` 关联到具体节或页码范围。

### 17.13 关系、样式和编号都应该是只读索引，热路径不要重复扫
**原始结论：** relationship、style、numbering 都应该先构建成只读索引；热路径上不要重复递归、重复扫描或依赖厚对象包装。

**是否接纳：** 接纳。

**接纳原因：** Word 文档的热路径很容易在重复 run、重复样式和重复链接上放大成本。只读索引比临时遍历更适合并发和重复查询。

**具体落实细节：** 当前 `RelationshipIndex` 继续保留；`StyleMap` 后续要加 memoization；`NumberingMap` 继续保持文档级只读定义，运行态计数由 `NumberingState` 持有，不跨文档共享。

### 17.14 调试和观测要可分级，默认策略要和开发阶段一致
**原始结论：** 调试输出应该可分级、可限额、可采样；profiling 和阶段级 metrics 也要保留。

**是否接纳：** 部分接纳。

**接纳原因：** 研究文档里“生产默认关闭 debug”的建议适合线上 wrapper，但我们现在还在结构迭代期，debug 常开对回归和审查更有价值。

**具体落实细节：** 当前 parser 维持 debug 常开，但文档里要补 `debug_level`、`debug_max_bytes_per_file`、`debug_sample_blocks` 和阶段 metrics。debug 只作为观测，不进入最终 LLM 输入。

### 17.15 错误和降级必须结构化，不能静默吞掉
**原始结论：** 错误应该区分 fatal、partial 和 warning，并带上 stage、part、locator 和 recoverable 信息；坏 block、坏 asset、坏公式都要能降级。

**是否接纳：** 接纳。

**接纳原因：** 这比“失败就全停”更适合批量解析，也比“悄悄吞掉异常”更适合调试和回归。

**具体落实细节：** 后续要扩展 warning 模型，把 stage 和 locator 加进去；坏对象可以降级成占位或 preview，但不能不留痕迹。当前 parser 里的 warning 机制已经是这条路的基础。

### 17.16 MarkItDown 的 registry 思路可借鉴，Markdown 兜底不适合当前目标
**原始结论：** converter registry、stream 位置恢复和 attempts 聚合值得借鉴，但把 DOCX 先转 HTML/Markdown 再回写，不适合作为当前 parser 的兜底链路。

**是否接纳：** 部分接纳。

**接纳原因：** registry 和失败诊断对工程组织有用；但 HTML/Markdown 会压扁 Word 原始结构，不符合我们“尽可能保留 Word 信息”的目标。

**具体落实细节：** 当前 parser 继续直接读 OOXML，不走 Markdown fallback。将来如果要做插件化 extractor 或 renderer，可以借 registry 和 attempts 聚合的思想，但不把 DOCX 先送去 HTML/Markdown 再绕回来。

### 17.17 批量解析必须避免输出目录冲突
**原始结论：** 批量 worker 如果只按 `stem` 写输出目录，重名文件会互相覆盖，甚至把 debug 和最终结果写乱。

**是否接纳：** 接纳。

**接纳原因：** 这不是一个小瑕疵，而是批量并发的正确性问题。只要同名文档出现一次，输出就可能被覆盖。

**具体落实细节：** `parse_many()` 后续要把输出目录改成与文件内容或 run id 相关的唯一目录，而不是简单的 `output_base / docx_stem`。如果暂时保留 stem 方案，开发文档里要把它明确标成待修复缺口。

总体上，这份调研文档最值得长期保留的，不是某个具体库的调用方式，而是它反复强调的边界：parser 负责安全读取 Word、构建结构、控制预算；上层负责存储、缓存和交互。凡是会把 parser 拉回平台壳、Markdown 兜底或厚对象模型的建议，都不应该照搬。
## 18. 参考资料

- Open XML SDK: [https://learn.microsoft.com/en-us/office/open-xml/open-xml-sdk](https://learn.microsoft.com/en-us/office/open-xml/open-xml-sdk)
- Open XML SAX/reader 思路: [https://learn.microsoft.com/en-us/office/open-xml/word/how-to-replace-text-in-a-word-document-with-sax](https://learn.microsoft.com/en-us/office/open-xml/word/how-to-replace-text-in-a-word-document-with-sax)
- WordprocessingML 文档结构: [https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document](https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document)
- WordprocessingML 表格: [https://learn.microsoft.com/en-us/office/open-xml/word/working-with-wordprocessingml-tables](https://learn.microsoft.com/en-us/office/open-xml/word/working-with-wordprocessingml-tables)
- Apache POI 文档组件: [https://poi.apache.org/components/document/index.html](https://poi.apache.org/components/document/index.html)
- docx4j: [https://github.com/plutext/docx4j](https://github.com/plutext/docx4j)
- python-docx: [https://python-docx.readthedocs.io/](https://python-docx.readthedocs.io/)
- ECMA-376 Office Open XML: [https://ecma-international.org/publications-and-standards/standards/ecma-376/](https://ecma-international.org/publications-and-standards/standards/ecma-376/)
