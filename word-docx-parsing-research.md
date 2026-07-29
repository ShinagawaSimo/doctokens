# Word 文档解析技术调研

调研日期：2026-07-27  
目标读者：第一次开始处理 Word 文档解析、抽取、转换或自动编辑工作的程序员。

## 1. 一句话结论

Word 文档解析的核心，不是“读取一个排版后的页面”，而是读取一个由多个 XML、二进制资源和关系文件组成的包。现代 `.docx` 文件本质上是：

```text
ZIP 容器 + Open Packaging Conventions(OPC) + Office Open XML(OOXML)
```

所以，解析 Word 文件时要把它当成一个“小型文件系统”来处理：

- 正文在 `word/document.xml`。
- 样式在 `word/styles.xml`。
- 编号在 `word/numbering.xml`。
- 图片在 `word/media/*`。
- 正文与图片、超链接、页眉页脚等对象之间的引用关系在 `word/_rels/document.xml.rels` 等 `.rels` 文件里。
- 表格、段落、文本、图片、图形不是同一种结构，需要分别处理。

如果你的目标是“抽取文本做搜索或 RAG”，可以忽略大量版式细节；如果你的目标是“保持 Word 原样显示或转换成 PDF/HTML”，那就必须理解样式、分页、字体、图片锚定、表格布局和不同编辑器的排版引擎差异。

## 2. 先区分几种 Word 文件

很多兼容性问题从文件类型就已经开始了。

| 扩展名 | 常见来源 | 技术特征 | 解析难度 |
|---|---|---|---|
| `.docx` | Microsoft Word 2007+、WPS、LibreOffice 等 | ZIP + OOXML | 中等，结构公开 |
| `.docm` | 含宏的 Word 文档 | ZIP + OOXML + VBA 宏项目 | 中等偏高，需注意安全 |
| `.dotx` / `.dotm` | Word 模板 | 与 `.docx/.docm` 类似，但作为模板使用 | 中等 |
| `.doc` | 旧版 Word 二进制格式 | 复合二进制文档，非 XML | 高 |
| `.wps` / `.wpt` | WPS Writer 自有格式 | WPS 自有/二进制格式 | 高，公开资料少 |
| `.rtf` | 富文本格式 | 文本型标记语言 | 中等 |
| `.pdf` | 固定版式输出 | 页面绘制结果，不是 Word 结构 | 与 Word 解析不同 |

对新项目来说，如果能控制输入格式，优先要求 `.docx`。如果必须支持 `.doc` 或 `.wps`，通常需要借助 LibreOffice、WPS、商业 SDK 或专门的转换服务先转成 `.docx`、HTML、PDF 或纯文本。

参考：

- [ECMA-376 Office Open XML 标准](https://ecma-international.org/publications-and-standards/standards/ecma-376/)
- [Microsoft Office 文件扩展名参考](https://learn.microsoft.com/zh-cn/office/compatibility/xml-file-name-extension-reference-for-office)
- [WPS 在线预览/编辑支持格式](https://open.wps.cn/documents/app-integration-dev/docs-center/online-preview-edit/format)

## 3. `.docx` 的包结构

把 `.docx` 改名为 `.zip` 后解压，通常能看到类似结构：

```text
[Content_Types].xml
_rels/
  .rels
docProps/
  core.xml
  app.xml
word/
  document.xml
  styles.xml
  numbering.xml
  settings.xml
  fontTable.xml
  media/
    image1.png
    image2.jpeg
  _rels/
    document.xml.rels
  theme/
    theme1.xml
  header1.xml
  footer1.xml
```

几个核心概念：

| 概念 | 作用 |
---|---|
| Part | 包里的一个文件，例如 `word/document.xml`、`word/styles.xml`、`word/media/image1.png` |
| Relationship | Part 之间的引用关系，例如正文里的图片 `rId5` 指向 `word/media/image1.png` |
| Content Type | 每个 Part 的 MIME 类型声明，放在 `[Content_Types].xml` |
| WordprocessingML | Word 正文、段落、表格、样式等 XML 词汇 |
| DrawingML | 图片、图形、图表等绘图相关 XML |
| VML | 旧版 Office 图形格式，仍可能在水印、文本框、兼容对象中出现 |

初学者最容易犯的错误是：只读 `word/document.xml`，然后以为已经读完全文档。实际上，页眉、页脚、脚注、尾注、评论、文本框、图片、图表和嵌入对象可能都在其他 Part 里。

参考：

- [WordprocessingML 文档结构](https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document)
- [Open XML 标记兼容性介绍](https://learn.microsoft.com/en-us/office/open-xml/general/introduction-to-markup-compatibility)

## 4. 文本是怎样存储的

Word 中用户看到的一段文字，在 OOXML 中大致是：

```xml
<w:p>
  <w:r>
    <w:t>Hello</w:t>
  </w:r>
  <w:r>
    <w:t> world</w:t>
  </w:r>
</w:p>
```

常见层级是：

```text
document
  body
    paragraph(w:p)
      run(w:r)
        text(w:t)
```

### 4.1 段落 paragraph

`w:p` 是段落。段落里可能有：

- 普通文本 run。
- 超链接。
- 图片。
- 字段，例如页码、目录、交叉引用。
- 批注锚点。
- 修订标记。
- 分页符、换行符。

### 4.2 run

`w:r` 是一段共享同一组字符格式的内联内容。一个句子可能被拆成很多 run，原因包括：

- 中间某几个字加粗、变色、改字体。
- Word 自动纠错或拼写检查留下内部标记。
- 复制粘贴造成格式碎片。
- 修订、批注、超链接、字段把文本切碎。

因此，不要假设一个自然语言句子对应一个 `w:t`。解析文本时，通常要把同一段落里的多个 run 合并成可读文本，但同时保留 run 的位置和格式信息，以便以后做高亮、批注或替换。

### 4.3 空格、换行和特殊字符

Word 文本里不只有 `w:t`：

| XML | 含义 |
---|---|
| `w:t` | 普通文本 |
| `w:tab` | 制表符 |
| `w:br` | 换行或分页 |
| `w:cr` | 回车 |
| `w:noBreakHyphen` | 不换行连字符 |
| `w:softHyphen` | 软连字符 |

如果只拼接 `w:t`，会丢失制表符、换行符、分页符等信息。

### 4.4 修订和批注

开启“修订”后，文档里会出现：

- `w:ins`：插入内容。
- `w:del`：删除内容。
- `w:moveFrom` / `w:moveTo`：移动内容。
- `w:commentRangeStart` / `w:commentRangeEnd`：批注范围。
- `word/comments.xml`：批注正文。

做解析时必须先决定策略：

| 策略 | 适用场景 |
---|---|
| 只读最终文本 | 搜索、RAG、摘要 |
| 同时读插入和删除 | 法务审阅、合同比对 |
| 保留修订结构 | 自动审稿、红线处理 |
| 接受全部修订后再读 | 文档归档、内容发布 |

## 5. 表格是怎样存储的

Word 表格的核心结构是：

```text
w:tbl
  w:tblPr      表格属性
  w:tblGrid    网格列定义
  w:tr         行
    w:tc       单元格
      w:p      单元格内段落
```

参考：[Working with WordprocessingML tables](https://learn.microsoft.com/en-us/office/open-xml/word/working-with-wordprocessingml-tables)

### 5.1 表格不是简单二维数组

刚开始写解析器时，很多人会把 Word 表格理解为：

```text
rows x columns
```

但真实 Word 表格更复杂：

- 横向合并：`w:gridSpan`。
- 纵向合并：`w:vMerge`。
- 单元格可以省略。
- 单元格内可以有多个段落。
- 单元格里可以嵌套表格。
- 表格列宽可能是固定值、百分比、自动适应。
- 表格可能跨页，表头可能重复。

因此，解析表格时建议构建一个规范化模型：

```text
Table
  rows[]
    cells[]
      rowIndex
      colIndex
      rowSpan
      colSpan
      text
      paragraphs[]
      nestedTables[]
      rawXml
```

如果只是做 CSV 导出，可以把合并单元格展开；如果要做高保真转换，则必须保留合并结构和宽度信息。

### 5.2 常见表格坑

| 问题 | 原因 | 建议 |
---|---|---|
| 单元格文本重复 | 合并单元格被库展开成多个逻辑格 | 保留 merge 信息或去重 |
| 列数不一致 | Word 允许行之间网格不完全一致 | 用 `tblGrid` 和单元格跨度重建网格 |
| 文本顺序奇怪 | 嵌套表格、文本框、批注混入 | 定义清晰的遍历顺序 |
| 转 HTML 后错位 | HTML table 模型和 Word 表格模型不同 | 明确处理 rowSpan / colSpan / width |
| 跨页表头丢失 | 只读正文结构，忽略 `w:tblHeader` | 解析行属性 |

## 6. 图片、图形和嵌入对象是怎样存储的

图片解析是 Word 处理中最容易出问题的部分之一。

正文里通常不会直接保存图片二进制，而是保存一个引用：

```xml
<a:blip r:embed="rId5"/>
```

然后在 `word/_rels/document.xml.rels` 里找到：

```xml
<Relationship
  Id="rId5"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
  Target="media/image1.png"/>
```

最终图片文件在：

```text
word/media/image1.png
```

### 6.1 图片分为 inline 和 anchor

Word 里图片有两种常见放置方式：

| 类型 | XML | 特点 | 解析/渲染风险 |
---|---|---|---|
| 嵌入型 | `wp:inline` | 像一个大字符，跟随文本流 | 较稳定 |
| 浮动/锚定型 | `wp:anchor` | 可以环绕文字、绝对定位、浮在页面上 | 高风险 |

本地 `documents` Skill 的图片审计脚本也特别区分这两类，因为浮动图片是 Word、LibreOffice、WPS 之间最常见的错位来源之一。相关脚本：

```text
C:/Users/Simo/.codex/plugins/cache/openai-primary-runtime/documents/26.723.12215/skills/documents/scripts/images_audit.py
```

### 6.2 图形不等于图片

Word 中的“视觉元素”可能是多种对象：

| 用户看到的对象 | 可能的底层结构 |
---|---|
| 普通图片 | DrawingML + image part |
| 形状 | DrawingML shape 或 VML |
| 文本框 | DrawingML/VML + 内部文本 |
| SmartArt | diagram parts |
| 图表 | chart parts + 可能关联 embedded xlsx |
| 公式 | Office Math ML |
| 嵌入 Excel | OLE object / embedded package |
| 水印 | 通常在页眉里的 VML shape |

所以，不能把所有视觉元素都当成 `word/media/*` 的图片。解析器需要先明确目标：

- 如果只要抽取图片文件，读 `image` relationship 即可。
- 如果要抽取图表数据，要解析 chart part 或嵌入表格。
- 如果要抽取文本框文字，需要解析 DrawingML/VML 内部文本。
- 如果要还原页面视觉位置，通常需要渲染引擎。

## 7. 样式和版式信息

Word 里文本看起来是什么样，通常不是直接写在每个字上，而是由多层规则叠加得到：

```text
默认样式
  + 段落样式
  + 字符样式
  + 表格样式
  + 编号样式
  + 主题字体/颜色
  + 直接格式
  + 兼容性设置
```

主要文件包括：

| 文件 | 作用 |
---|---|
| `word/styles.xml` | 段落、字符、表格、列表样式 |
| `word/numbering.xml` | 项目符号和编号定义 |
| `word/theme/theme1.xml` | 主题颜色和字体 |
| `word/settings.xml` | 兼容性、修订、文档设置 |
| `word/fontTable.xml` | 字体表 |

初学者要特别注意：正文 XML 里出现的 `Heading1`、`Normal`、`ListParagraph` 等只是样式 ID，不代表最终字号、缩进、颜色已经在正文里展开。要获得“最终样式”，需要把样式继承链解析出来。

## 8. 页眉页脚、脚注尾注、目录和字段

完整解析 Word 文档时，正文只是其中一部分。

| 内容 | 常见位置 |
---|---|
| 页眉 | `word/header*.xml` |
| 页脚 | `word/footer*.xml` |
| 脚注 | `word/footnotes.xml` |
| 尾注 | `word/endnotes.xml` |
| 批注 | `word/comments.xml` |
| 样式 | `word/styles.xml` |
| 编号 | `word/numbering.xml` |
| 文档属性 | `docProps/core.xml`, `docProps/app.xml` |

### 8.1 字段不是普通文本

目录、页码、交叉引用、日期等常用字段表示，例如：

- `TOC`：目录。
- `PAGE`：页码。
- `NUMPAGES`：总页数。
- `REF`：交叉引用。
- `SEQ`：题注编号。

字段可能有“缓存显示文本”，但缓存不一定最新。很多库只读到缓存文本，不会重新计算字段。要获得准确页码和目录，通常需要 Word、LibreOffice 或其他排版引擎更新字段。

## 9. 常见开源库和工具路线

不同库解决的问题不同。选型前先问自己：我是要抽文本、改文档、转 HTML、做预览，还是要高保真渲染？

### 9.1 Python 生态

| 工具 | 定位 | 优点 | 局限 |
---|---|---|---|
| `python-docx` | `.docx` 创建和编辑 | API 简单，段落/表格/样式/图片常规操作方便 | 对浮动图形、复杂字段、批注、修订等支持有限 |
| `docx2python` | 内容抽取 | 能抽正文、页眉页脚、脚注尾注、图片、批注等 | 主要面向抽取，不是高保真编辑 |
| `docx2txt` | 轻量文本/图片抽取 | 简单好用 | 结构信息少 |
| `mammoth` | `.docx` 转干净 HTML | 适合语义化内容发布 | 有意不追求精确版式 |
| `python-pptx` 等同族库 | 类似对象模型思路 | 风格类似 | 不是 Word 专用 |
| `lxml + zipfile` | 直接解析 OOXML | 最灵活，可处理库不支持的细节 | 需要理解 OOXML |

参考：

- [python-docx 文档](https://python-docx.readthedocs.io/)
- [python-docx shapes 分析](https://python-docx.readthedocs.io/en/latest/dev/analysis/features/shapes/index.html)
- [docx2python](https://github.com/ShayHill/docx2python)
- [Mammoth](https://github.com/mwilliamson/python-mammoth)

### 9.2 Java / .NET 生态

| 工具 | 定位 | 优点 | 局限 |
---|---|---|---|
| Open XML SDK | .NET 官方/事实标准 OOXML SDK | 与 Microsoft 文档生态贴近，适合底层 OOXML 操作 | 需要理解包结构和 XML |
| Apache POI XWPF | Java 解析/编辑 `.docx` | Java 项目常用，支持段落、表格、图片等 | 复杂版式和完整 OOXML 覆盖仍有限 |
| docx4j | Java OOXML 绑定和转换 | 模型完整，适合深度处理和转换 | 学习成本较高 |
| Apache Tika | 文档文本抽取和索引 | 支持格式多，适合搜索/检索 | 不适合高保真编辑 |

参考：

- [Open XML SDK 文档](https://learn.microsoft.com/en-us/office/open-xml/open-xml-sdk)
- [Apache POI 文档组件](https://poi.apache.org/components/document/index.html)
- [docx4j](https://github.com/plutext/docx4j)
- [Apache Tika](https://tika.apache.org/)

### 9.3 JavaScript / 浏览器生态

| 工具 | 定位 | 优点 | 局限 |
---|---|---|---|
| `docx` | 生成 `.docx` | JS 生成 Word 文档方便 | 不是通用解析器 |
| `docx-preview` / `docxjs` | 浏览器预览 `.docx` | 可把 Word 渲成 HTML/CSS 预览 | 与 Word 实际排版不完全一致 |
| `mammoth.js` | `.docx` 转 HTML | 语义化转换 | 不追求像素级还原 |
| `JSZip + DOMParser` | 直接解析 OOXML | 灵活 | 需要自己处理关系和 XML |

参考：

- [docxjs / docx-preview](https://github.com/VolodymyrBaydalka/docxjs)
- [Mammoth JS](https://github.com/mwilliamson/mammoth.js)

### 9.4 转换器和渲染器

| 工具 | 定位 | 典型用途 |
---|---|---|
| LibreOffice headless | 文档转换/渲染 | `.docx` 转 PDF/图片、批量转换 |
| Pandoc | 文档格式转换 | `.docx` 与 Markdown、HTML、LaTeX 等互转 |
| Word COM / Office Automation | 调用本机 Word | Windows 环境下高保真处理，但服务端风险高 |
| OnlyOffice / Collabora | 在线编辑/渲染 | Web 文档服务 |

参考：

- [Pandoc 手册](https://pandoc.org/MANUAL.html)
- [LibreOffice 命令行帮助](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)

### 9.5 AI / RAG 文档解析工具

| 工具 | 定位 | 适合场景 |
---|---|---|
| Unstructured | 文档分块和结构化抽取 | RAG、信息抽取 |
| Docling | 文档解析、布局理解、结构化输出 | 多格式文档理解 |
| LangChain loaders | 封装各种解析器 | 快速接入 RAG |
| LlamaIndex readers | 文档读取和索引 | RAG 数据接入 |

这类工具通常不追求 Word 编辑器级别的视觉还原，而是把文档拆成标题、段落、表格、图片说明等“可用于检索和模型理解”的元素。

## 10. 本地 `documents` Skill 的处理思路

本地 `documents` Skill 的路径：

```text
C:/Users/Simo/.codex/plugins/cache/openai-primary-runtime/documents/26.723.12215/skills/documents/SKILL.md
```

它的核心路线很典型：

1. 常规创建/编辑用 `python-docx`。
2. `python-docx` 不支持的功能，直接 patch OOXML。
3. 图片、表格、批注、修订、字段等分别有专项脚本。
4. 任何布局敏感结果都要用 LibreOffice 渲染成 PNG，再人工/程序检查。

典型脚本：

| 脚本 | 作用 |
---|---|
| `render_docx.py` | DOCX 转 PDF/PNG 做视觉 QA |
| `scripts/images_audit.py` | 审计图片、区分 inline/anchor、解析关系目标 |
| `scripts/docx_table_to_csv.py` | 表格导出 CSV |
| `scripts/docx_ooxml_patch.py` | 修订、批注、超链接、字段等底层 OOXML patch |
| `scripts/table_geometry.py` | 表格宽度、网格、单元格宽度审计和修正 |

这体现了一个实用原则：高层库负责 80% 常规结构，底层 XML 负责 20% 复杂功能，最后用真实渲染检查版式。

## 11. 初学者推荐解析架构

如果你要从零写一个 Word 解析流程，建议不要一开始就追求“完整复刻 Word”。先按目标分层。

### 11.1 第一步：定义目标

| 目标 | 推荐策略 |
---|---|
| 搜索/全文索引 | 抽纯文本，保留标题、段落、表格文本 |
| RAG | 抽结构化 block，做分块，保留页眉/标题/表格上下文 |
| 表格导出 | 专门解析 `w:tbl`，处理合并单元格 |
| 图片提取 | 扫关系文件和 `word/media` |
| 转 HTML | 用 Mammoth/Pandoc/docxjs，再按业务修正 |
| 自动编辑 Word | 用 `python-docx` / Open XML SDK / docx4j |
| 高保真渲染 | 调 LibreOffice/Word/OnlyOffice，而不是自己实现排版 |

### 11.2 第二步：建立中间模型

不要让业务逻辑直接依赖 OOXML 细节。建议先转成自己的中间模型：

```text
Document
  metadata
  sections[]
  blocks[]
    Paragraph
      style
      runs[]
    Table
      rows[]
    Image
      relationshipId
      path
      altText
    Heading
      level
    Footnote
    Comment
```

这样后续无论输出 JSON、Markdown、HTML、CSV，还是喂给大模型，都更稳定。

### 11.3 第三步：保留原始定位信息

解析时建议保留：

- 源 Part 路径：例如 `word/document.xml`、`word/header1.xml`。
- XML 节点路径或自定义 block id。
- 关系 ID：例如 `rId5`。
- 样式 ID：例如 `Heading1`。
- 表格行列坐标和合并信息。
- 图片文件路径和尺寸。
- 原始 XML 片段，便于无法解析时兜底。

这些信息对调试、回写、定位错误非常重要。

## 12. Python 入门示例

### 12.1 查看 `.docx` 包内容

```python
from zipfile import ZipFile

docx_path = "sample.docx"

with ZipFile(docx_path) as z:
    for name in z.namelist():
        print(name)
```

### 12.2 用 `python-docx` 读取段落和表格

```python
from docx import Document

doc = Document("sample.docx")

for i, p in enumerate(doc.paragraphs):
    text = p.text.strip()
    if text:
        print("PARA", i, text)

for ti, table in enumerate(doc.tables):
    print("TABLE", ti)
    for row in table.rows:
        print([cell.text for cell in row.cells])
```

注意：这段代码读不到所有复杂对象，例如文本框、部分浮动图片、页眉页脚里的内容、批注、修订删除文本等。

### 12.3 直接读取图片关系

```python
from zipfile import ZipFile
from lxml import etree

NS = {
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

with ZipFile("sample.docx") as z:
    rels_xml = z.read("word/_rels/document.xml.rels")
    root = etree.fromstring(rels_xml)

    for rel in root.findall("rel:Relationship", namespaces=NS):
        rel_type = rel.get("Type", "")
        if rel_type.endswith("/image"):
            print(rel.get("Id"), rel.get("Target"))
```

### 12.4 如果要检查图片在正文中的位置

需要同时解析正文 `word/document.xml`：

```python
from zipfile import ZipFile
from lxml import etree

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

with ZipFile("sample.docx") as z:
    xml = z.read("word/document.xml")
    root = etree.fromstring(xml)

    for inline in root.findall(".//wp:inline", namespaces=NS):
        blip = inline.find(".//a:blip", namespaces=NS)
        if blip is not None:
            print("inline image", blip.get("{%s}embed" % NS["r"]))

    for anchor in root.findall(".//wp:anchor", namespaces=NS):
        blip = anchor.find(".//a:blip", namespaces=NS)
        if blip is not None:
            print("floating image", blip.get("{%s}embed" % NS["r"]))
```

## 13. 为什么 Word 和 WPS 打开同一个文件会错乱

这个问题可以拆成两种情况。

### 13.1 情况一：根本不是同一种文件格式

如果一个文件是 `.wps` 或 `.wpt`，它并不是 Microsoft Word 的 `.docx`。Word 或其他软件打开它时需要转换。转换过程无法保证所有格式、对象和排版规则一一对应。

同理，旧 `.doc` 是二进制 Word 格式，也不是 `.docx`。从 `.doc` 转 `.docx` 本身就可能改变结构。

### 13.2 情况二：都是 `.docx`，但 OOXML 方言和扩展不同

OOXML 有标准，但真实 Office 文档会包含：

- Transitional 与 Strict 差异。
- Microsoft Word 扩展。
- WPS 自己写入或兼容处理的扩展。
- `mc:Ignorable` 可忽略命名空间。
- `mc:AlternateContent` 备用内容。
- 旧版 VML 对象。
- 应用私有设置。

Microsoft 也公开维护了 Word 对 OOXML 的扩展说明，例如 MS-DOCX；Office 实现细节也有 MS-OE376 这类资料。也就是说，标准只是共同基础，真实编辑器还会有各自实现和扩展。

参考：

- [MS-DOCX: Word Extensions to the Office Open XML Structure](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-docx/)
- [MS-OE376: Office Implementation Information for ECMA-376](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/)

### 13.3 情况三：版式不是文件里“固定保存”的

`.docx` 保存的是结构和约束，不是每一页的最终像素。

例如文档里会保存：

- 页宽页高。
- 页边距。
- 段前段后距。
- 字体名。
- 表格宽度。
- 图片锚点。
- 是否与下段同页。
- 兼容性选项。

但最终页面上每一行怎么断、每个字宽多少、图片压住哪里、表格在哪一页断开，是由编辑器的排版引擎计算出来的。

Word、WPS、LibreOffice 的排版引擎不同，所以可能出现：

| 现象 | 技术原因 |
---|---|
| 同一段文字换行不同 | 字体度量、字距、中文标点压缩、断行算法不同 |
| 页数不同 | 换行差异累积导致分页变化 |
| 图片偏移 | `wp:anchor`、环绕方式、相对定位解释不同 |
| 表格溢出或变窄 | 表格自动适应、列宽计算、单元格边距算法不同 |
| 页眉页脚错位 | 节属性、首页不同、奇偶页不同解释不同 |
| 文本框位置变 | VML/DrawingML 支持和兼容逻辑不同 |
| 字体变化 | 本机缺字或字体名映射不同 |
| 目录/页码不准 | 字段缓存未更新或更新算法不同 |

### 13.4 情况四：兼容模式和旧版布局规则

Word 有兼容模式，用来让旧文档尽量保持旧版 Word 的布局。兼容模式会影响可用功能和布局行为。一个文档在 Word 中可能被当成某个旧版本兼容布局处理，而在 WPS 中可能按另一套规则处理。

参考：[Microsoft Office 兼容模式管理](https://learn.microsoft.com/zh-cn/office/compatibility/manage-compatibility-mode-for-office)

### 13.5 情况五：保存时被重写

Word 和 WPS 都可能在保存时重写 OOXML：

- 重排 XML 节点。
- 改写样式默认值。
- 把某些对象转换成兼容对象。
- 丢弃自己不理解的扩展。
- 更新字段缓存。
- 改写图片压缩和尺寸。
- 改变编号定义。

因此，“用 A 打开、用 B 保存、再用 A 打开”可能比“只用 B 打开看一眼”风险更高。

## 14. 哪些内容最容易导致兼容性问题

按风险从高到低大致是：

1. 浮动图片、环绕图片、绝对定位对象。
2. 文本框、形状、SmartArt、图表、公式、OLE 嵌入对象。
3. 复杂表格：合并单元格、跨页、自动列宽、嵌套表格。
4. 多节文档：横竖版混排、不同页眉页脚。
5. 复杂编号：多级列表、自定义编号样式。
6. 字段：目录、交叉引用、页码、题注编号。
7. 兼容模式文档。
8. 缺失字体，尤其是中文字体和企业定制字体。
9. 修订、批注、内容控件。
10. 旧版 `.doc`、WPS `.wps` 与 `.docx` 来回转换。

## 15. 解析项目的工程建议

### 15.1 不要一开始就自己实现完整 Word

自己实现 Word 排版引擎几乎不可行。更现实的方式是：

- 抽取文本：用现成库。
- 复杂结构：直接读 OOXML。
- 高保真显示：调用 Word/LibreOffice/OnlyOffice/WPS 渲染。
- 自动编辑：高层库 + OOXML patch。

### 15.2 先定义“保真等级”

| 等级 | 目标 | 示例 |
---|---|---|
| L1 文本保真 | 文本基本完整 | 搜索索引、摘要 |
| L2 结构保真 | 标题、段落、表格、图片顺序正确 | RAG、知识库 |
| L3 语义保真 | 样式、编号、批注、脚注、字段可识别 | 审阅、合规 |
| L4 视觉近似 | HTML/PDF 预览接近 Word | 在线预览 |
| L5 像素级保真 | 与 Word 打开效果一致 | 正式发布、合同、印刷 |

不同等级的成本差异很大。很多业务只需要 L2 或 L3，不需要 L5。

### 15.3 建议的处理流水线

```text
输入文件
  -> 判断格式和安全检查
  -> 如果不是 docx，先转换或拒绝
  -> 解包 docx
  -> 读取 content types 和 relationships
  -> 解析正文、页眉页脚、脚注尾注、评论
  -> 解析段落、run、表格、图片、字段
  -> 建立中间模型
  -> 业务处理
  -> 输出 JSON / Markdown / HTML / CSV / DOCX
  -> 如果布局敏感，渲染检查
```

### 15.4 安全注意事项

Word 文件可能来自不可信用户，解析时要注意：

- ZIP 炸弹。
- 路径穿越。
- 超大 XML。
- 外部关系链接。
- 宏文件 `.docm`。
- OLE 嵌入对象。
- 恶意图片或嵌入包。
- 加密文档。

对服务端解析系统来说，最好在沙箱里处理文件，限制 CPU、内存、磁盘和网络访问。

## 16. 推荐选型

### 16.1 Python 后端

| 需求 | 推荐 |
---|---|
| 快速抽段落和表格 | `python-docx` |
| 抽较完整内容 | `docx2python` |
| 转干净 HTML | `mammoth` |
| 深度处理 OOXML | `zipfile + lxml` |
| RAG 文档分块 | Unstructured / Docling / 自定义中间模型 |
| 最终渲染检查 | LibreOffice headless |

### 16.2 Java 后端

| 需求 | 推荐 |
---|---|
| 常规 `.docx` 解析 | Apache POI XWPF |
| 深度 OOXML 操作 | docx4j |
| 搜索索引文本抽取 | Apache Tika |
| 高保真转换 | LibreOffice / OnlyOffice / 商业 SDK |

### 16.3 .NET 后端

| 需求 | 推荐 |
---|---|
| OOXML 读写 | Open XML SDK |
| 调用本机 Word | Office Interop / COM，适合桌面自动化，不适合普通服务端 |
| 服务端转换 | LibreOffice / 商业 SDK / 云服务 |

### 16.4 前端浏览器

| 需求 | 推荐 |
---|---|
| 简单预览 | docx-preview / docxjs |
| 语义 HTML | mammoth.js |
| 高保真在线编辑 | OnlyOffice / Collabora / WPS Web SDK 等 |

## 17. 实战检查清单

开始做 Word 解析前，建议逐项确认：

- 输入是否只支持 `.docx`？
- 是否需要支持 `.doc`、`.docm`、`.wps`？
- 要不要读取页眉页脚？
- 要不要读取脚注尾注？
- 要不要读取批注？
- 修订内容是接受、拒绝，还是全部保留？
- 表格是否需要保留合并单元格？
- 图片是否只要文件，还是要位置？
- 文本框里的文字是否需要抽取？
- 图表数据是否需要抽取？
- 目录和页码是否需要重新计算？
- 输出是 JSON、Markdown、HTML、PDF 还是新的 DOCX？
- 是否要求和 Word/WPS 打开视觉一致？
- 是否有安全沙箱？
- 是否有渲染回归测试？

## 18. 最小可行方案

如果你是第一次做，建议从这个版本开始：

1. 只支持 `.docx`。
2. 用 `python-docx` 读取正文段落和表格。
3. 用 `zipfile + lxml` 读取图片关系和 `word/media`。
4. 先忽略浮动图形、文本框、SmartArt、OLE。
5. 输出一个结构化 JSON。
6. 收集失败样例，再逐步补齐复杂对象。

示例 JSON 可以长这样：

```json
{
  "metadata": {
    "filename": "sample.docx"
  },
  "blocks": [
    {
      "type": "paragraph",
      "style": "Heading1",
      "text": "项目背景"
    },
    {
      "type": "paragraph",
      "style": "Normal",
      "text": "这里是正文。"
    },
    {
      "type": "table",
      "rows": [
        ["姓名", "角色"],
        ["张三", "开发"]
      ]
    },
    {
      "type": "image",
      "relationshipId": "rId5",
      "target": "word/media/image1.png",
      "placement": "inline"
    }
  ]
}
```

这个模型不完美，但足够让业务先跑起来，并且以后可以扩展。

## 19. 最重要的工程判断

Word 解析没有一个“万能库”。真正稳定的方案通常是组合拳：

```text
高层库读取常规结构
+ 直接 OOXML 处理复杂对象
+ 转换器处理旧格式
+ 渲染器验证最终版式
+ 针对业务建立中间模型
```

如果只做内容理解，不要被版式拖垮；如果要保证版式，就不要只相信 XML 抽取结果，必须渲染验证。

## 20. 参考资料

官方规范与文档：

- [ECMA-376 Office Open XML](https://ecma-international.org/publications-and-standards/standards/ecma-376/)
- [Microsoft Open XML SDK](https://learn.microsoft.com/en-us/office/open-xml/open-xml-sdk)
- [WordprocessingML 文档结构](https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document)
- [Working with WordprocessingML tables](https://learn.microsoft.com/en-us/office/open-xml/word/working-with-wordprocessingml-tables)
- [Open XML 标记兼容性](https://learn.microsoft.com/en-us/office/open-xml/general/introduction-to-markup-compatibility)
- [MS-DOCX Word 扩展规范](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-docx/)
- [MS-OE376 Office 对 ECMA-376 的实现信息](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/)
- [Microsoft Office 文件扩展名参考](https://learn.microsoft.com/zh-cn/office/compatibility/xml-file-name-extension-reference-for-office)
- [Microsoft Office 兼容模式](https://learn.microsoft.com/zh-cn/office/compatibility/manage-compatibility-mode-for-office)
- [WPS 支持格式](https://open.wps.cn/documents/app-integration-dev/docs-center/online-preview-edit/format)

开源库与工具：

- [python-docx](https://python-docx.readthedocs.io/)
- [docx2python](https://github.com/ShayHill/docx2python)
- [Mammoth](https://github.com/mwilliamson/python-mammoth)
- [Apache POI](https://poi.apache.org/components/document/index.html)
- [docx4j](https://github.com/plutext/docx4j)
- [Apache Tika](https://tika.apache.org/)
- [Pandoc](https://pandoc.org/MANUAL.html)
- [docxjs / docx-preview](https://github.com/VolodymyrBaydalka/docxjs)
- [LibreOffice 命令行参数](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)

