# PPTX 输出格式规范

> 本文档定义 `pptx_llm_parser` 的输出契约，是解析器行为与测试 golden 的权威依据。
> 设计意图与决策理由见 `docs/design-notes.md` §13 与 `docs/PPTX开发大纲.md`（docs/ 目录被 .gitignore 排除）。

## 总体设计

三种密度（与 DOCX/XLSX 同一枚举）：

| 密度 | 文件名 | 内容 |
|---|---|---|
| `semantic`（默认） | `parsed.html` | 完整结构 + 坐标/占位符/内联格式（主题色解析后） |
| `structural` | `structural.html` | 块级结构 + 语义对象（链接/批注/表格/对象引用），无坐标无视觉格式 |
| `plain` | `plain.txt` | 纯文本流，`=== Slide N ===` 分隔幻灯片 |

输出首行恒为密度标记：`density=semantic` / `density=structural` / `density=plain`。

```python
from pptx_llm_parser import parse_pptx, write_document, Density

html = parse_pptx("deck.pptx")                                  # semantic（默认）
html = parse_pptx("deck.pptx", density=Density.STRUCTURAL)
path = write_document("deck.pptx", "out", density=Density.PLAIN)
```

## 隐式闭合规则

块级元素省略闭合标签（每块独占一行），内联元素保留闭合标签：

- 隐式闭合：`<slide>`、`<title>`、`<p>`、`<tr>`、`<td>`、`<img>`、`<table>`、`<chart>`、`<smartart>`、`<media>`、`<notes>`、`<comment>`
- 显式闭合：`<b>`、`<i>`、`<u>`、`<color>`、`<a>`

## 阅读顺序（几何排序）

三种密度的默认块序为**几何排序**：top→bottom 为主、left→right 为次（比较 `(y, x)` 的稳定排序，同坐标平局保持 XML 文档顺序即 z-order）。无坐标的形状（自身无 `a:xfrm` 且无布局继承几何）排在末尾、保持相对 XML 序。

几何排序是 declared 坐标数据上的确定性规则，不是推断。z-order 以 `z=N` 属性在 semantic 输出（N 为形状在 `p:spTree` 文档顺序中的 1 基序号），供重叠关系裁决。

坐标以**千分比**输出（`x/y/w/h` = EMU 相对 `p:sldSz` ×1000 的四舍五入整数）；`sldSz` 缺失时降级为无坐标。

## 块级元素清单

### `<slide n=N [hidden]>`

每张幻灯片一个；`n` 为 sldIdLst 中的 1 基序号；隐藏幻灯片（`p:sld show="0"`）加 `hidden`。semantic 与 structural 输出，plain 用 `=== Slide N ===` 文本分隔（隐藏标记仅 structural/semantic）。

### `<title>` 与 `<p>`

文本形状。占位符类型（`p:ph@type`，自身声明优先、否则按 idx 从布局继承）为 `title`/`ctrTitle` 时输出 `<title>`，其余输出 `<p>`。

属性（semantic）：`id=sN`（形状序号）、`ph=类型`、`x/y/w/h`（千分比，有坐标时）、`z=N`、`name="..."`（cNvPr 名称，含空格时加引号）。
属性（structural）：仅 `ph`。

### `<img id=imgN [alt="..."]>`

图片形状。`id` 为资产 id（`imgN`，包级确定性计数，与 OCR 开关无关）；`alt` 来自 `cNvPr@descr`。外部图片（`TargetMode=External`）只记录 URL、绝不下载。semantic 附加 `x/y/w/h/z/name`。

### `<table id=sN rows=R cols=C [truncated]>`

表格（graphicFrame → a:tbl）。行：`<tr>` 独占一行；单元格：`<td>文本</td>`（显式闭合、tab 不参与）。structural/semantic 超 30 行截断并加 `truncated`（截断行数与完整行数列于 `rows=`）；plain 超 10 行截断并输出 `[Table truncated: R rows, C cols]`。

### `<chart id=chartN type=T series=S points=P truncated>`

图表（graphicFrame → chart part，经共享 chart_ml 解析）。`truncated` 恒存在：正文是摘要视图，完整 series 数据经 `get_resource("chart", id)` 获取。

### `<smartart id=smartartN type=布局 nodes=N links=M truncated>节点文本…`

SmartArt（diagram 数据模型）。节点文本以空格连接附在标签之后（modelId 已重映射为 1 基序数）。`type` 来自 diagramLayout 的 `dgm:cat@type` URI 尾段。

### `<media id=mediaN kind=video|audio>`

视频/音频（p14:media）。`kind` 来自 `p:videoFile`/`p:audioFile` 检测；plain 输出 `[Video]`/`[Audio]`/`[Media]`。

### `<notes>文本</notes>`

演讲者备注，紧跟所属幻灯片内容之后（幻灯片 = 自包含原子块）。plain 为幻灯片文本后的 `[Notes: 文本]`。无备注不输出。

## 内联元素清单（仅 semantic 包裹格式）

| 元素 | 来源 | 示例 |
|---|---|---|
| `<b>` / `<i>` / `<u>` | `a:rPr` 的 b/i/u | `<b>粗体</b>` |
| `<color value=#RRGGBB>` | `a:rPr/a:solidFill` 解析后 | `<color value=#FF0000>红</color>` |
| `<a href=URL>` | `a:hlinkClick`（rPr 级） | `<a href=https://example.test>链接</a>` |

嵌套顺序（外→内）：`a` > `b` > `i` > `u` > `color`。

**主题色管线**：`schemeClr` 经 clrMap 四级映射（slide clrMapOvr > slide clrMap > layout clrMap > master clrMap > 规范默认 tx1→dk1/tx2→dk2/bg1→lt1/bg2→lt2）→ theme1.xml clrScheme 12 槽（缺失回退 Office 默认主题）→ `lumMod`/`lumOff` HSL 亮度变换 → `tint`/`shade` 线性混合。**近黑过滤**：解析结果接近默认黑（max(R,G,B)≤48 且色偏≤16）时不输出 color——默认文字色不产生噪声。

run 级 IR 只在形状含格式/链接时进入输出（全纯文本形状仅输出扁平 `text`）。

## 补充内容区域 `<!-- supplemental -->`

structural/semantic 在全部幻灯片之后输出批注区；plain 以文本区块 `[Comments]` 输出：

```
<!-- supplemental -->
<comment id=cmtN [author=…] [date=…] [parent=IDX]>文本
```

现代（p15）线程批注：`parentId` 保留线程关系输出为 `parent=IDX`（IDX 为被回复批注的原始 idx）；作者名经 commentAuthors.xml 解析。PPTX 批注是包级注释（无幻灯片锚点），故不输出行内引用标记。legacy 批注仅检测 + 警告。

## 密度差异对照

| 元素 | plain | structural | semantic |
|---|---|---|---|
| slide 边界 | `=== Slide N ===` | `<slide n=N [hidden]>` | 同左 |
| 标题 | 纯文本 | `<title>` | `<title>` + 全属性 |
| 文本形状 | 纯文本 | `<p [ph]>` | `<p>` + id/ph/坐标/z/name |
| 内联格式 | 剥离 | 剥离 | `<b>/<i>/<u>/<color>` + `<a>` |
| 图片 | `[Image: alt]` / `[Image]` | `<img id alt>` | 同左 + 坐标/z/name |
| 表格 | tab 分隔（10 行截断） | `<table>`（30 行截断） | 同左 + 坐标/z/name |
| 图表 | `[Chart: type, N series]` / `[Chart]` | `<chart … truncated>` | 同左 + 坐标/z/name |
| SmartArt | `[SmartArt: layout, N nodes]` / `[SmartArt]` | `<smartart …>节点文本` | 同左 + 坐标/z/name |
| 媒体 | `[Video]`/`[Audio]`/`[Media]` | `<media id kind>` | 同左 + 坐标/z/name |
| 备注 | `[Notes: 文本]` | `<notes>` | 同左 |
| 批注 | `[Comments]` + `[cmtN: 文本]` | `<comment …>` 区 | 同左 |
| 隐藏标记 | 无 | `hidden` | `hidden` |
| 继承来源 | 无 | 无 | 无（仅 debug JSON） |

## 特殊约定

- **占位符是声明角色**：`p:ph@type` 是权威声明但不保证文本语义；slide 形状无 ph 时按 idx 从布局继承。
- **模板文字不混入正文**：layout/master 的 txBody 文本永不读取（仅用于几何/类型/颜色继承）。
- **无文本形状**：plain/structural 完全丢弃；semantic 中同样不输出（M4 阶段）——装饰折叠（`ParseOptions.collapse_repeated_shapes`）为 backlog。
- **背景**：`p:bg` 为 backlog 项（设计契约见 docs/PPTX开发大纲.md §5.10，OCR 提升路径随 OCR 里程碑落地）。
- **组合形状/动画/切换/自定义放映/节**：v1 不解析，检测到未知形状类型输出警告并继续。
- **资产惰性**：图片/媒体二进制在解析期绝不读取，按需经 `get_resource`（M5）获取。
- **失败软降级**：悬空关系/缺失 part/畸形值 → `ParseWarning`（含 code 与 locator）并继续解析，绝不中断。

## 公共 API

```python
parse_pptx(source, *, density=SEMANTIC, stream=False, options=None) -> str | Iterator[str]
iter_slides(source, *, density=SEMANTIC, start_slide=1, options=None) -> Iterator[str]
render_window(source, *, slide, span=1, density=SEMANTIC, options=None) -> str
get_resource(source, resource_type, resource_id, *, rows=None, columns=None,
             aggregate=None, aggregate_column=None, options=None) -> str | None
write_document(source, output_dir, *, density=SEMANTIC, options=None) -> Path
```

- `iter_slides`：每幻灯片一个 chunk（首个 chunk 含 `density=` 头行），批注为尾部独立 chunk；`start_slide` 1 基。`parse_pptx(stream=True)` 等价于 `iter_slides`。
- `render_window`：`slide` 1 基，`slide=-1` 选最后一页，`span` 越界截断在末尾；越界窗口渲染为仅含密度头的空文档。
- `get_resource`：
  - `image` / `media` → 内嵌二进制的 base64（解析期惰性，此处才读 ZIP）；external 资产与未知 id 返回 None
  - `chart` → 全量 series 记录（name/categories/values/min/max）
  - `smartart` → 节点/链接全量记录
  - `table` → 完整表格（不受 30 行截断），`rows="a-b"` 行切片（1 基含两端）、`columns=[i...]` 列筛选、`aggregate=sum|count|avg|min|max` 配合 `aggregate_column` 输出 `<aggregate op=… column=… value=…>`（数值单元格按文本强转，非数值跳过）
  - 复数类型（`images` 等）抛 ValueError；`resource_type` 接受 `ResourceType` 枚举或字符串
- 表格资源 id 为包级 `tableN`（解析器按出现顺序分配，与幻灯片无关；渲染输出中的 `id=sN` 是幻灯片内序号，两者不可混用）。

## 未实现（backlog）

- `ParseOptions.ocr` —— 图片 OCR（`<ocr-text>` 兄弟元素契约，同 DOCX §12 架构）
- 背景 `p:bg`（契约见 docs/PPTX开发大纲.md §5.10，OCR 提升路径随之落地）
- 组合形状 grpSp 递归与组坐标换算；装饰折叠 `collapse_repeated_shapes`
