# DOCX Parser 性能优化设计文档

日期：2026-07-29  
版本：v0.1  
状态：开发中

## 1. 背景与动机

项目是一个纯 Python 3 stdlib 的 DOCX→LLM 语义 XML 解析器（~3660 行）。当前 4.5MB docx 解析耗时 404ms（无 debug），其中 body 解析占 307ms（76%）。

用户探索了引入 python-docx/lxml 简化代码的可行性，分析结论：
- python-docx 引入重依赖但实际可简化的代码不到 200 行，收益极低
- lxml 对纯 iterparse 无加速（实测 0.9x），但对频繁 find/findall 操作的编译 XPath 可加速

最终决定：不引入 python-docx，但探索 lxml 优化和无依赖优化两条路线，在两个 git 分支上并行开发，benchmark 对比后选优。

## 2. 分支策略

```
master (当前 4e6bd16)
  ├── perf/lxml-optimization    → 方案B：引入 lxml 编译 XPath
  └── perf/arch-optimization    → 方案C：无依赖优化 + 架构调整
```

## 3. 性能基线（master, 4.5MB docx, debug=False）

| 阶段 | 耗时 | 占比 |
|---|---|---|
| body 解析 | 307ms | 76% |
| assets 导出 | 50ms | 12% |
| ancillary | 22ms | 5% |
| 其余 | 25ms | 6% |
| **总计** | **404ms** | — |

Body 解析内部分解：
- iterparse 原始遍历：~130ms（43%）
- 每段落 run 提取 + 格式 + inline 对象：~177ms（57%）

## 4. 方案B：lxml 编译 XPath（分支 perf/lxml-optimization）

### 4.1 核心策略

引入 lxml（仅 lxml.etree，不引入 python-docx），利用预编译 XPath 加速热路径中的 find/findall 操作。

### 4.2 改动清单

| 文件 | 改动 | 预期收益 |
|---|---|---|
| `core/constants.py` | 新增 `lxml_helpers.py`：预编译 XPath 对象 + lxml 版 helper 函数 | 基础层 |
| `extractors/inline.py` | `_parse_run()` 中 find 替换为预编译 XPath；`_drawing_objects()` 同理 | -40~60ms |
| `extractors/body.py` | iterparse 引擎可选切换为 lxml | -10~20ms |
| `extractors/ancillary.py` | 复用的 InlineParser 自动获得 lxml 加速 | -5~10ms |
| `core/models.py` | `ParseOptions` 新增 `use_lxml: bool = False` | 开关 |

### 4.3 预编译 XPath 示例

```python
# lxml_helpers.py（新增）
from lxml import etree

# 预编译热路径 XPath
X_W_RPR = etree.XPath("./w:rPr", namespaces=NS_MAP)
X_W_T = etree.XPath("./w:t", namespaces=NS_MAP)
X_W_DRAWING = etree.XPath("./w:drawing", namespaces=NS_MAP)
X_A_BLIP = etree.XPath(".//a:blip", namespaces=NS_MAP)
# ... 约 15-20 个高频查询
```

### 4.4 预期结果

- body 解析：307ms → 180-200ms（35-40% 提升）
- 总耗时：404ms → 270-300ms
- 新增依赖：lxml（C 扩展，~5MB）

## 5. 方案C：无依赖优化 + 架构调整（分支 perf/arch-optimization）

### 5.1 核心策略

不改依赖，纯代码级优化：
1. 预计算所有常用 qn() 标签名
2. InlineParser 单次遍历替代多次 find
3. debug 写入异步化
4. assets 导出并行化
5. 热路径 dataclass 加 __slots__

### 5.2 改动清单

| 文件 | 改动 | 预期收益 |
|---|---|---|
| `core/constants.py` | 预计算 30-40 个常用 qn() 标签为模块常量；优化 local_name() | -5~10ms |
| `extractors/inline.py` | `_parse_run()` 改为单次迭代 children 按 tag 分发 | -30~50ms |
| `core/debug.py` | DebugWriter 新增 write_json_async()，ThreadPoolExecutor(1) | debug 模式 -180ms |
| `extractors/assets.py` | 多图片导出 ThreadPoolExecutor 并行 | -20~35ms |
| `core/models.py` | StyleRecord/RelationshipRecord/ParseWarning 加 __slots__ | -5ms |
| `core/metrics.py` | 热路径 stage() context manager 减少对象创建 | -3ms |

### 5.3 关键改动细节

#### 5.3.1 预计算标签名

```python
# core/constants.py 新增
# 预计算热路径标签，避免每次 qn() 做 f"{{{ns}}}{local}" 字符串拼接
_TAG_W_R = qn("w", "r")
_TAG_W_RPR = qn("w", "rPr")
_TAG_W_PPR = qn("w", "pPr")
_TAG_W_T = qn("w", "t")
# ... 30+ 个
```

#### 5.3.2 单次遍历替代多次 find

```python
# 当前（多次独立扫描）
rpr = first_child(run, "w", "rPr")
drawing = first_child(run, "w", "drawing")
# ... 每次 O(n)

# 改进后（一次迭代）
for child in run:
    lname = _local_name_fast(child.tag)
    if lname == "rPr":
        rpr = child
    elif lname == "drawing":
        drawing = child
    # ... 一次 O(n)
```

#### 5.3.3 debug 异步写入

```python
class DebugWriter:
    def __init__(self, ...):
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._futures: list[Future] = []

    def write_json_async(self, filename, data):
        """异步写入 debug JSON，不阻塞主解析流程。"""
        self._futures.append(
            self._executor.submit(self._write_json_sync, filename, data)
        )

    def wait_all(self):
        """等待所有异步写入完成（在 render 之前调用）。"""
        for f in self._futures:
            f.result()
        self._futures.clear()
```

### 5.4 预期结果

- body 解析：307ms → 200-230ms（25-30% 提升）
- 总耗时（无 debug）：404ms → 280-320ms
- debug 模式：644ms → ~400ms（debug 写入异步化）
- 零新增依赖

## 6. 对比基准与验证方法

### 6.1 Benchmark 脚本

```bash
# 在每个分支上运行
python -c "
import time
from pathlib import Path
from docx_llm_parser import DocxParser, ParseOptions

for f in Path('.').glob('*.docx'):
    for _ in range(3):
        t0 = time.perf_counter()
        p = DocxParser().parse(f, ParseOptions(debug=False, output_dir=Path('out/_bench')))
        print(f'{f.name}: {time.perf_counter()-t0:.3f}s')
        print(f'  stages: {p.metrics[\"stagesMs\"]}')
"
```

### 6.2 验收标准

- 所有现有测试通过（`python -m pytest tests/ -v`）
- 输出 parsed.xml 内容与 master 一致（内容 diff 无差异）
- body 解析阶段耗时相比 master 基线至少有 15% 以上的下降

## 7. 风险与注意事项

- **方案B**：lxml 的 iterparse 在 tag 过滤时与我们当前的无过滤遍历语义略有不同，需小心
- **方案B**：lxml 的 `elem.clear()` 行为与 stdlib 一致，但内存释放时机可能不同
- **方案C**：异步 debug 写入需要确保在 render 阶段之前完成（`wait_all()`）
- **两者**：都要保证 `test_inline_renderer.py` 全部通过
- **两者**：代码改动处添加中文注释说明优化意图

## 8. 开发顺序

1. 从 master 创建 `perf/arch-optimization` 分支，实现方案C
2. 从 master 创建 `perf/lxml-optimization` 分支，实现方案B
3. 分别 benchmark
4. 对比结果，合并优胜分支到 master
