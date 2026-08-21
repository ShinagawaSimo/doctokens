# PPTX 解析输出格式说明

本文档面向下游开发者和 LLM tool description 编写者，解释 `pptx-llm-parser` 输出的语义 HTML5 标记格式。

## 总体设计

解析器将 `.pptx` 文件转化为三种密度的输出：

| 密度 | 枚举值 | 文件 | 内容 |
|---|---|---|---|
| 语义级 | `SEMANTIC` (`"semantic"`) | `parsed.html` | 完整 HTML5 标记，含形状坐标、占位符类型、内联格式和对象引用 |
| 结构级 | `STRUCTURAL` (`"structural"`) | `structural.html` | 块级结构 + 语义对象，去除坐标与粗体/斜体/颜色等视觉格式 |
| 纯文本 | `PLAIN` (`"plain"`) | `plain.txt` | 纯文本流，幻灯片间以 `=== Slide N ===` 分隔；备注拼接在本页幻灯片之后，批注拼接在文末 |

输出第一行标记密度：

```
density=semantic
density=structural
density=plain
```

下文以 semantic 为准介绍完整格式。structural 和 plain 分别是 semantic 的逐级精简。

## 隐式闭合规则

块级元素省略闭合标签。当一个块级元素结束时，由下一个块级元素或文档结束隐式表示。

**隐式闭合的块级元素**：`<slide>`、`<title>`、`<p>`、`<tr>`、`<td>`、`<img>`、`<table>`、`<chart>`、`<smartart>`、`<media>`、`<notes>`、`<comment>`

**显式闭合的内联元素**：`<a>`、`<b>`、`<i>`、`<u>`、`<color>`

```
示例：
<slide n=1>                           ← 无闭合标签
<title>季度汇报                       ← 无闭合标签
<p>正文内容                           ← 无闭合标签
<b>粗体</b>                          ← 内联元素需要显式闭合
```

## 阅读顺序

幻灯片内的形状按几何位置**从上到下、从左到右**输出（先比较纵向、再比较横向）。没有坐标的形状排在末尾。该顺序是确定性的：同一份文件每次解析顺序一致。

原始文档顺序（z-order，即形状的叠放次序）以 `z=N` 属性在 semantic 密度输出，供重叠元素的层级关系判断。

坐标 `x/y/w/h` 是相对幻灯片宽高的**千分比**（0–1000 的整数）。

## 块级元素清单

### 幻灯片 `<slide>`

```
<slide n=1>
<title>…</title>
…
<slide n=2 hidden>
```

- `n`：幻灯片序号（从 1 开始，按演示顺序）
- `hidden`：隐藏幻灯片标记
- plain 密度以 `=== Slide N ===` 文本行分隔幻灯片（不含 hidden 标记）

### 标题 `<title>` 与段落 `<p>`

文本形状按占位符类型输出为 `<title>`（类型为 `title`、`ctrTitle`）或 `<p>`（其余情况）。

```
<title id=s1 ph=title x=0 y=100 w=100 h=50 z=1 name="标题 1">季度汇报
<p id=s2 ph=body x=0 y=500 w=200 h=100 z=2 name="内容占位符 2">第一行
第二行
```

- `id`：形状序号（幻灯片内，仅 semantic）
- `ph`：占位符类型（`title`、`body`、`subTitle`、`ctrTitle` 等）。仅当形状声明了占位符角色时输出
- `x/y/w/h`：千分比坐标（仅 semantic）
- `z`：z-order 序号（仅 semantic）
- `name`：形状名称（仅 semantic，含空格时加引号）
- 形状内多个段落以单个 `\n` 连接；structural 仅保留 `ph` 属性，plain 为纯文本

### 图片 `<img>`

```
<img id=img1 alt="图表截图">
<img id=img1 alt="图表截图" x=0 y=800 w=100 h=100 z=3 name="图片 3">
```

- `id`：图片资源 id（`get_resource` 按此 id 获取图片内容）
- `alt`：替代文本（仅非空时输出）
- semantic 附加坐标与 z/name 属性；plain 以 `[Image: 描述]` 或 `[Image]` 占位

### 表格 `<table>`

```
<table id=s4 rows=2 cols=2>
<tr><td>A</td><td>B</td>
<tr><td>C</td><td>D</td>
```

- `id`：形状序号（幻灯片内）
- `rows` / `cols`：总行数 / 总列数（截断时仍显示完整行数）
- 大表格（>30 行）标记 `truncated`，仅输出前 30 行；plain 以 `\t` 分隔单元格、>10 行截断并附加 `[Table truncated: R rows, C cols]`
- 完整表格（含行切片、列筛选、聚合）经 `get_resource(source, "table", "table1")` 获取；表格资源 id 为包级 `tableN`

### 图表 `<chart>`

```
<chart id=chart1 type=bar series=2 points=4 truncated>
```

- `id`：图表资源 id（`get_resource` 按此 id 获取完整数据点）
- `type`：图表类型（bar/line/pie/scatter/bubble/area/radar/surface 等）
- `series`：系列数
- `points`：总数据点数
- 所有图表均标记 `truncated`，完整系列数据（类目、数值、范围）通过 `get_resource` 获取
- plain 以 `[Chart: bar, 2 series]` 占位

### SmartArt `<smartart>`

```
<smartart id=smartart1 type=process nodes=3 links=2 truncated>开始 判断 结束
```

- `id`：SmartArt 资源 id（`get_resource` 按此 id 获取完整节点和连接）
- `type`：布局类型（process/cycle/hierarchy 等）
- `nodes`：节点数
- `links`：边数
- 全部节点文本（空格分隔）附在标签之后
- 总是标记 `truncated`，完整结构（含节点 id 和连接关系）通过 `get_resource` 获取
- plain 以 `[SmartArt: process, 3 nodes]` 占位

### 媒体 `<media>`

```
<media id=media1 kind=video>
```

- `id`：媒体资源 id（`get_resource` 按此 id 获取媒体内容）
- `kind`：`video` / `audio`
- plain 以 `[Video]` / `[Audio]` / `[Media]` 占位

### 备注 `<notes>`

```
<notes>本页演讲提示
```

演讲者备注紧跟所属幻灯片内容之后输出（幻灯片保持自包含）。plain 为该页文本之后的 `[Notes: 内容]`。无备注的幻灯片不输出。

## 内联元素清单

### 文本格式

```
<b>粗体</b>
<i>斜体</i>
<u>下划线</u>
```

### 颜色 `<color>`

```
<color value=#FF0000>红色文字</color>
```

`value` 为 CSS 颜色值（`#RRGGBB`）。主题色（如"强调文字颜色 1"）输出解析后的实际色值；接近默认黑色的颜色不输出（避免噪声）。

### 超链接 `<a>`

```
<a href=https://example.com>链接文字</a>
```

`href` 为外部链接 URL。外部资源只记录、不下载。

## 补充内容区域 `<!-- supplemental -->`

全部幻灯片结束后输出批注完整内容（structural 与 semantic）：

```
<!-- supplemental -->
<comment id=cmt1 author=Alice date=2026-08-13T10:00:00>评论内容
<comment id=cmt2 author=Bob date=2026-08-13T11:00:00 parent=1>回复内容
```

- `id`：批注标识符（cmtN）
- `author`、`date`：作者和日期（仅存在时输出）
- `parent`：被回复批注的原始编号（线程回复）
- plain 以 `[Comments]` 文本区输出，每条为 `[cmtN: 内容]`

## 密度差异对照

| 元素 | semantic | structural | plain |
|---|---|---|---|
| 幻灯片 | `<slide n=N [hidden]>` | 同 semantic | `=== Slide N ===` 文本行 |
| 标题 | `<title>` + 全属性 | `<title>` | 纯文本 |
| 段落/文本形状 | `<p>` + id/ph/坐标/z/name | `<p ph=...>` | 纯文本 |
| 粗体/斜体/下划线/颜色 | `<b>` `<i>` `<u>` `<color value=>` | 全部去除 | 无 |
| 超链接 | `<a href=...>` | `<a href=...>` | 纯文本 |
| 图片 | `<img id alt>` + 坐标 | `<img id alt>` | `[Image: 描述]` / `[Image]` |
| 表格 | 完整 HTML 表格 + 30 行截断 | 同 semantic | `\t` 分隔纯文本，>10 行截断 |
| 图表 | `<chart>` + 属性 + `truncated` | 同 semantic | `[Chart: ...]` 纯文本摘要 |
| SmartArt | `<smartart>` + 属性 + 节点文本 + `truncated` | 同 semantic | `[SmartArt: ...]` 纯文本摘要 |
| 媒体 | `<media id kind>` + 坐标 | `<media id kind>` | `[Video]` / `[Audio]` / `[Media]` |
| 备注 | `<notes>` | `<notes>` | `[Notes: 内容]` |
| 批注 | supplemental 区 | supplemental 区 | `[Comments]` 文本区 `[cmtN: 内容]` |
| 坐标（x/y/w/h/z/name） | 全部输出 | 不输出 | 不输出 |
| 隐藏标记 | `hidden` | `hidden` | 无 |

## 公共 API

```python
from pptx_llm_parser import parse_pptx, iter_slides, render_window, get_resource, Density

html = parse_pptx("deck.pptx")                                     # semantic（默认）
html = parse_pptx("deck.pptx", density=Density.STRUCTURAL)
```

| 函数 | 语义 |
|---|---|
| `parse_pptx(source, *, density, stream, options)` | 解析为指定密度的完整输出；`stream=True` 时返回逐幻灯片的分块迭代器（同 `iter_slides`） |
| `iter_slides(source, *, density, start_slide, options)` | 每张幻灯片一个分块；首个分块含密度标记行；批注为尾部独立分块 |
| `render_window(source, *, slide, span, density, options)` | 渲染指定幻灯片窗口；`slide` 从 1 开始，`slide=-1` 表示最后一页，`span` 越界时截断 |
| `get_resource(source, resource_type, resource_id, *, rows, columns, aggregate, aggregate_column, options)` | 按需提取单个资源（见下表） |

## 资源提取 API

正文中被截断的资源（`<table truncated>`、`<chart ... truncated>`、`<smartart ... truncated>`）可通过 `get_resource` 按需获取完整数据：

| 调用 | 返回 |
|---|---|
| `get_resource(source, "image", "img1")` | 图片内容（base64） |
| `get_resource(source, "media", "media1")` | 媒体内容（base64） |
| `get_resource(source, "chart", "chart1")` | 完整图表数据（每个系列的类目、数值、最小/最大值） |
| `get_resource(source, "smartart", "smartart1")` | 完整节点列表和连接关系 |
| `get_resource(source, "table", "table1")` | 完整表格（不受截断限制） |
| `get_resource(source, "table", "table1", rows="2-5")` | 指定行范围（1-based，含起止行） |
| `get_resource(source, "table", "table1", columns=[0, 2])` | 仅指定列（0-based 序号） |
| `get_resource(source, "table", "table1", aggregate="sum", aggregate_column=1)` | 聚合值，支持 sum/count/avg/min/max |

`rows` 和 `columns` 可组合使用。`aggregate` 基于表格文本中的数值计算，不做公式重算。`resource_type` 接受字符串或 `ResourceType` 枚举；复数形式（如 `"images"`）报错，请使用单数。

## 特殊约定

- 所有方括号标记（如 `[Image]`、`[Chart: ...]`、`[Notes: ...]`、`[cmtN: ...]`）是 plain 专用的纯文本占位符，不出现在 structural/semantic 中
- 属性值含空格或特殊字符时使用双引号包裹并进行 HTML 转义
- 资源 id（`imgN`、`mediaN`、`chartN`、`smartartN`、`tableN`）在同篇文档多次解析中保持一致
- 幻灯片模板中的占位提示文字（如"单击此处添加标题"）不会出现在输出中
- 主题色输出解析后的实际色值；接近默认黑色的颜色不输出
- `truncated` 标记的语义：正文是摘要视图，完整数据通过 `get_resource` 按需获取
- 外部链接的资源（图片、媒体）只记录、不下载，也不在输出中展开内容
