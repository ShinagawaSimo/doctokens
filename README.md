# docx-llm-parser

实际对话场景中，用户对 DOCX 文档常有以下类型的需求：

* 这篇文档第3页概括了哪些内容？

* 能不能帮我获取文章脚注中引用的文献？

* 文章中标红的部分能被怎么优化修改？

当前市场中常见的agent工具中，DOCX解析流程基本会直接使用发展成熟的各种 DOCX 解析库，如`Docling`、`MarkItDown`、`PanDoc`等，将`.docx`转化为markdown格式文本进行读取。然而它们都没有为实际与docx相关的需求进行优化设计，只是忠实地执行了转化成markdown的任务，LLM常常无法从解析结果中获取到足以完成任务的信息。

常见的docx解析流程通常会面对以下问题：

* 脚注、尾注、编号、文本框文字等文字信息丢失；
* 下划线、文字颜色、高亮、上下标等内联格式未处理(大部分库只处理粗体、斜体)；
* 嵌套表格、图表、SmartArt等复杂结构无法获得信息；
* **文字所在页数信息无法获取**。这明明是常见的需求场景，然而现有流程基本都完全没有进行处理，LLM既不能从解析结果中直接获得页数信息，也不能获取到字体、行距等信息稍作估算，通常只能乱猜一个范围或者重问一次；
* 精度更高的解析工具，往往依赖重、速度慢；
* 采用markdown之外的其它格式作为解析结果，往往浪费token；
* 模型无法控制自己获取的信息的密度，获取到的大量格式信息可能对简单需求(如"为我概括这篇文章")毫无用处，同样是对token的浪费。

`docx-llm-parser` 是一个专为 **LLM 下游消费** 设计的 DOCX 解析库，解决了以上所有的问题，在设计之初便遵循以下理念：

1. **忠于实际对话需求**。
   
   * 所有的在原始DOCX文档中出现的文字信息，均会以合适的方式进入文字流；
   
   * 在最高信息密度等级的解析中，文本的各种格式数据均被妥善地处理；(字体及字号信息被有意地排除在外；能有"帮我总结微软雅黑字体的14号字的内容"这种需求的人，就让大模型生成脚本狠狠地耗他的token吧。)
   
   * `<page = x>`的标记将会出现在对应页面的第一个段落前，并提供页码窗口区间读取工具；
   
   * 复杂结构可以选择性解析并读取。

2. **极致轻量化**。
   
   * **不依赖于任何第三方库**(包括`python-docx`)、系统级工具、GPU模型，即插即用。
   
   * 解析流程以流式读取和按需提取为主，避免为简单问题加载不必要的重型转换链路。

它把 Word 文档转化为结构清晰、信息密集、token 高效的语义 HTML5 标记，让 LLM 能够精确地理解文档的每一个组成部分——而不仅仅是"一堆文字"。

### 为什么需要它？

当你把 Word 文档直接喂给 LLM 时，通常会面临三种困境：

1. **用 `python-docx` 或 Pandoc 提取纯文本**——失去了标题层级、表格结构、自动编号、脚注引用。LLM 看到的是一堵"文字墙"，分不清哪里是标题、哪里是正文、哪里是表格数据。
2. **用 MarkItDown 或 Docling 转 Markdown**——格式广度很好，但表格合并单元格消失了、编号序列断裂了、图表变成了空白、修订追踪完全丢失。转换链路越长，信息丢失越多。
3. **直接把原始 XML 丢给 LLM**——OOXML 命名空间冗长、标签噪音极大、token 消耗惊人，LLM 要花大量上下文窗口去理解 XML 结构而非文档内容。

`docx-llm-parser` 解决了这三个问题：它**直接解析 OOXML 源文件**，提取文档中所有确凿存在的结构信息，然后以**极致 token 效率**的语义 HTML5 输出——让 LLM 读到的是信息而非噪音。

### 突出特点

**零依赖架构（仅 Pillow）**

不依赖 `python-docx`、不依赖系统级工具（LibreOffice/Word COM）、不依赖 GPU 模型。使用 Python 标准库的 `xml.etree.ElementTree.iterparse` 流式解析 OOXML，内存占用可控。唯一的第三方库是 Pillow，仅用于压缩超大嵌入图片以控制下游 base64 token 消耗。

**最深的结构解析**

与市面上通用格式转换器不同，`docx-llm-parser` 只做一件事——把 DOCX 的结构信息完整、准确地提取出来：

- **标题识别来自 `w:outlineLvl` 样式链**，不做启发式推断（不会因为一段文字字号大就把它当标题）。
- **自动编号恢复**——从 `numbering.xml` 解析抽象编号定义和实例覆盖，精确推进计数器，还原 Word 中可见的 "3.1.2" 式编号文本。
- **完整的表格网格重建**——包括 `colspan`、`rowspan`、`vMerge` 垂直合并、嵌套表格。不只是把单元格文字按行列排出来。
- **图表和 SmartArt 的轻量数据摘要**——提取图表类型、标题、系列数据点，以及 SmartArt 的节点文本和连接关系。
- **修订追踪**——支持 `final`（接受所有修改）、`original`（拒绝所有修改）、`review`（保留修订标记）三种读取策略。
- **OMML 原生公式**——Word 的数学公式转为可读文本表示。
- **域代码语义解析**——区分超链接、页码引用、交叉引用，而非把它们当成普通文本。

**极致 token 效率**

这是 `docx-llm-parser` 区别于所有竞品的核心优势。每一个设计决策都围绕"让 LLM 用更少的 token 获得更多的信息"：

- **隐式闭合 HTML5**：块级元素（`<h1>` 到 `<h6>`、`<p>`、`<td>`、`<th>`、`<tr>` 等）省略闭合标签，由下一个块级元素的开始隐式表示前者的结束。实测节省约 **31% 的结构标签 token**。
- **单字符属性名**：`h` 替代 `href`、`i` 替代 `id`、`g` 替代 `page`、`v` 替代 `value`——每个属性节省 2-5 个字符，在包含大量表格和超链接的文档中积累显著。
- **三密度分级输出**：LLM 可以按需选择粒度——概括全文用 L0（纯文本），定位段落用 L1（块级结构 + 语义对象），精细分析用 L2（完整语义 + 格式信息）。不需要为一个简单问题消耗全文的 L2 token。
- **图片压缩**：超过 1MB 的嵌入图片自动缩放至 2000px + JPEG 重编码，控制下游 base64 token 消耗。
- **页面窗口读取**：基于 OOXML 分页标记的精确页面定位，LLM 可以按页读取而非一次加载全文。

**LLM 工具调用专用的 API 设计**

`docx-llm-parser` 的 API 是围绕 LLM 的工作模式设计的：

- `build_manifest(parsed)` — LLM 在首次接触文档前先了解文档规模（多少页、多少表格、多少脚注），再决定用什么密度、读多少页。
- `render_window(parsed, page=..., span=..., density=...)` — 按页码范围精确读取，`page=-1` 语法糖直接读取最后一页。
- `list_resources(parsed, type)` / `get_resource(parsed, type, id)` — 无需读取全文即可获取图片、图表、SmartArt 和表格资源，LLM 按需精读。

### 设计哲学

`docx-llm-parser` 遵循三条原则，它们定义了什么是"该做的"和"不该做的"：

1. **只输出 OOXML 中确凿存在的信息**。不根据字号、加粗、文本长度等信号猜测标题或结构。Word 文档中看起来像标题但缺少 `w:outlineLvl` 的段落，会被当作普通段落处理——因为那正是 OOXML 认为它是什么。

2. **LLM 是能推断结构的读者**。解析器的职责是忠实提取，不是替 LLM 做语义判断。如果文档没有使用 Heading 样式，`build_manifest()` 返回的标题数为 0——这本身就是有用信息（告诉 LLM "此文档无结构化层级，需要自行理解"）。

3. **错误的结构标记比没有结构标记更糟糕**。漏掉一个标题，LLM 仍能从上下文和文本内容推断；错误地把一段普通文本标记为标题，会污染整个文档的结构理解。

### 与常用方案的比较

| 场景            | python-docx / docx2txt | Pandoc / MarkItDown | Docling / Unstructured | **docx-llm-parser**      |
| ------------- | ---------------------- | ------------------- | ---------------------- | ------------------------ |
| 简单段落提取        | ✅                      | ✅                   | ✅                      | ✅                        |
| 标题层级（来自样式）    | 需手动读取                  | ✅                   | ⚠ 部分启发式                | ✅ `w:outlineLvl`         |
| 自动编号恢复        | ❌                      | ✅                   | ❌                      | ✅                        |
| 合并单元格表格       | ❌                      | ⚠ 部分支持              | ❌                      | ✅ colspan/rowspan/vMerge |
| 图表 / SmartArt | ❌                      | ❌                   | ❌                      | ✅ 轻量摘要                   |
| 修订追踪          | ❌                      | ✅                   | ❌                      | ✅ 三策略                    |
| 脚注拼接（L0）      | ❌                      | ❌                   | ❌                      | ✅                        |
| Token 优化      | ❌                      | ❌                   | ❌                      | ✅ 隐式闭合+短属性+密度            |
| 安装复杂度         | 轻量                     | 中等                  | 重量（模型+系统依赖）            | 极轻（Pillow 单依赖）           |

---

## 安装

```bash
pip install -e .
```

Python ≥ 3.10。依赖：Pillow ≥ 10.0。

## 快速开始

```python
from pathlib import Path

from docx_llm_parser import ParseOptions, parse_docx, write_document

output_dir = Path("out") / "example"
parsed = parse_docx("example.docx", ParseOptions(debug=True, output_dir=output_dir))
html_path = write_document(parsed, output_dir, density="L2")  # "L0" | "L1" | "L2"
```

### 分步使用

```python
from pathlib import Path

from docx_llm_parser import ParseOptions, parse_docx, render_document, write_document

# 解析（产出 ParsedDocument 中间模型）
parsed = parse_docx(
    "example.docx",
    ParseOptions(debug=True, output_dir=Path("out/example")),
)

# 渲染
html_text = render_document(parsed, density="L2")                 # 返回字符串
html_path = write_document(parsed, Path("out/example"), density="L2")  # 写入 parsed.html
```

### 三种密度

| 密度     | 输出                          | 典型场景             |
| ------ | --------------------------- | ---------------- |
| **L0** | 纯文本，段落间 `\n\n` 分隔           | 概括全文、分类、提取关键词    |
| **L1** | 块级 HTML5（无粗体/斜体/颜色等格式）      | 定位段落、对比段落、读取表格   |
| **L2** | 完整语义 HTML5（含所有格式 + 链接 + 公式） | 理解格式语义、链接目标、公式结构 |

每种密度下脚注/尾注/页码/表格的处理策略不同。L0 将脚注文本拼接到引用段落末尾，尾注拼接到文档末尾，表格退化为 `\t` 分隔文本；L1/L2 保留引用标记并将完整内容放在 independent 区域。

### 多文档并发

```python
from pathlib import Path

from docx_llm_parser import parse_many

results = parse_many(
    ["doc1.docx", "doc2.docx", "doc3.docx"],
    output_base=Path("out/batch"),
)
for result in results:
    print(result.docx, result.ok, result.output_path, result.error)
```

## 高级 API

### `build_manifest(parsed)` — 文档元信息

```python
from docx_llm_parser import build_manifest

info = build_manifest(parsed)
# {"pages": 23, "tables": 5, "images": 12, "footnotes": 45, "endnotes": 3, "comments": 7}
```

### `render_window(parsed, page, span, density)` — 页码范围窗口

```python
from docx_llm_parser import render_window

content = render_window(parsed, page=3)                          # 第 3 页，L2
content = render_window(parsed, page=5, span=3, density="L1")    # 第 5-7 页，L1
last_page = render_window(parsed, page=-1)                       # 最后一页（page=-1 语法糖）
```

页码来自 OOXML 中的显式分页标记（`w:br w:type="page"` + `w:lastRenderedPageBreak`）。

### `list_resources()` / `get_resource()` — 独立资源提取

```python
from docx_llm_parser import get_resource, list_resources

images = list_resources(parsed, "images")          # 所有图片清单
charts = list_resources(parsed, "charts")          # 所有图表摘要
tables = list_resources(parsed, "tables")          # 所有逻辑表格摘要
image = get_resource(parsed, "image", "img3")      # 单张图片详情
table = get_resource(parsed, "table", "t2")        # 完整逻辑表格
```

无需读取全文即可获取资源列表，供 LLM 按需精读。

## 解析能力

### 支持的文档结构

| 元素                    | 说明                                                  |
| --------------------- | --------------------------------------------------- |
| **标题** `<h1>`–`<h6>`  | 仅来自 `w:outlineLvl` 样式链，不做启发式推断                      |
| **段落** `<p>`          | 内联格式：粗体、斜体、下划线、删除线、上标/下标、颜色、高亮、小型大写字母               |
| **表格** `<table>`      | 网格重建、`colspan`/`rowspan`/`vMerge`、嵌套表、表头识别          |
| **自动编号**              | 从 `numbering.xml` 还原可见编号文本（如 "3.1.2"），含计数器推进        |
| **超链接** `<a h=...>`   | 内部书签 + 外部 URL                                       |
| **公式** `<eq>`         | OMML 原生公式 → 可读文本                                    |
| **图表** `<chart>`      | 类型、标题、系列数据摘要                                        |
| **SmartArt** `<sa>`   | 节点文本 + 连接关系                                         |
| **图片** `<img>`        | 嵌入图片导出到 `assets/`，超过 1MB 时自动缩放 + JPEG 压缩            |
| **文本框** `<tb>`        | DrawingML / VML 文本框内容提取                             |
| **脚注 / 尾注**           | 引用标记 + 正文区域独立展示                                     |
| **批注**                | 引用标记 + 正文区域独立展示                                     |
| **页眉 / 页脚**           | 正文区域独立展示                                            |
| **修订追踪**              | `final`（接受所有修改）、`original`（拒绝所有修改）、`review`（保留修订标记） |
| **域代码**               | 超链接域、页码引用、交叉引用                                      |
| **分页标记** `<page n=N>` | `w:lastRenderedPageBreak` + `w:br w:type="page"`    |

### 设计哲学

- **只输出 OOXML 中确凿存在的信息**。不根据字号、加粗、文本长度猜测标题或结构。
- **LLM 是能推断结构的读者**。解析器的职责是忠实提取，不是替 LLM 做语义判断。
- **错误的结构标记比没有结构标记更糟糕**。漏掉一个标题 LLM 仍能从文本推断；错误标记一段正文为标题会污染文档结构。

## 输出结构

```
out/<docx_stem>/
  parsed.html         # L2 完整语义 HTML5
  l1.html             # L1 块级结构
  l0.txt              # L0 纯文本
  assets/             # 导出图片（img1_hash.png, ...）
  .debug/             # debug=True 时的中间产物（blocks.json, styles.json, metrics.json 等）
```

## HTML5 约定

块级元素（`<h1>`–`<h6>`, `<p>`, `<table>`, `<tr>`, `<th>`, `<td>` 等）采用隐式闭合：省略 `</h1>`、`</p>` 等闭合标签，由下一个块级元素的开始隐式表示前者结束。这减少了约 31% 的标签 token。

属性名使用单字符缩写以进一步节省 token：

| 属性   | 含义          | 属性  | 含义           |
| ---- | ----------- | --- | ------------ |
| `i`  | id          | `h` | href         |
| `g`  | page（页码）    | `s` | span         |
| `rs` | rowSpan     | `v` | value（颜色/高亮） |
| `f`  | file        | `k` | kind（图表类型）   |
| `t`  | title       | `n` | name / count |
| `p`  | point count | `a` | author       |
| `d`  | date        |     |              |

## 公开 API

| 函数                                                             | 说明                            |
| -------------------------------------------------------------- | ----------------------------- |
| `parse_docx(path, options?)`                                   | 解析单个 DOCX，返回 `ParsedDocument` |
| `render_document(parsed, *, density?)`                         | 将已解析文档渲染为字符串                  |
| `iter_document(parsed, *, density?)`                           | 流式迭代渲染片段                      |
| `write_document(parsed, output_dir, *, density?)`              | 原子写出目标密度文件                    |
| `render_window(parsed, *, page, span?, density?)`              | 返回指定页码范围的内容片段                 |
| `build_manifest(parsed)`                                       | 返回文档元信息（页数、表格数、图片数等）          |
| `list_resources(parsed, type)`                                 | 列出指定复数资源（图片/图表/SmartArt/表格）   |
| `get_resource(parsed, type, id)`                               | 获取单个资源详情                      |
| `parse_many(paths, output_base)`                               | 多文档并发解析（`ThreadPoolExecutor`） |

## 运行测试

```bash
python -m pytest tests/ -v
```
