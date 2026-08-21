# Source 能力契约设计

**日期**: 2026-08-03
**状态**: 已实施

## 动机

source 插件的四项能力（search / novel_info / chapter_list / chapter_content）是隐式约定——没有 ABC、没有 Protocol、没有类型签名契约。新人加 source 全靠模仿现有目录。

**痛点**:
1. 函数签名错了编译期不报错，运行时 `registry.resolve()` 拿到函数直接调，炸在用户脸上
2. 四个函数的参数各不相同（search 接受 query，novel_info 接受 url，chapter_content 接受 chapter），但没有任何地方声明这个差异
3. 引入新能力（比如 comments、reviews）需要在 FUNC_FILE_MAP、capabilities()、resolve() 三处同步修改

## 设计决策表

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 契约形式 | ABC（继承强制）/ Protocol（结构子类型）/ 无 | **Protocol** | 不改动 24 个现有源文件，纯增量；Protocol 只要求满足结构，无需显式继承 |
| 类型注解严格度 | 精确导入模型类 / `Any` | **Any** | 避免 sources ↔ core 循环导入风险；Protocol 仅作文档/IDE 提示，不跑 mypy |
| 能力元数据 | 保留 FUNC_FILE_MAP / 单一 CAPABILITY_META | **CAPABILITY_META** | 消除三处同步修改痛点；新增能力类型只需加一条 |
| 源发现机制 | 静态列表 / 文件系统扫描 | **文件系统扫描（保持现状）** | 新增源只需创建目录+文件，零注册表修改 |
| 运行时校验 | 不做 / mypy / inspect.signature | **inspect.signature** | 不引入 dev 依赖；校验参数名缺失是最常见错误 |
| 校验粒度 | 参数名 + 类型 / 仅参数名 | **仅参数名** | 类型校验需 mypy/pyright，且现有 24 个返回注解不一致 |

## 实现

### 1. `novelbase/sources/contracts.py`（新建）

- 4 个 `typing.Protocol` 类：`SearchFunc` / `NovelInfoFunc` / `ChapterListFunc` / `ChapterContentFunc`
- `CAPABILITY_META` 字典：`{能力名: {file_stem, required_params}}`，替代 FUNC_FILE_MAP

```python
CAPABILITY_META = {
    "search":          {"file_stem": "search",          "required_params": ("query", "engine")},
    "novel_info":      {"file_stem": "novel_info",      "required_params": ("url", "engine")},
    "chapter_list":    {"file_stem": "chapter_list",    "required_params": ("url", "engine")},
    "chapter_content": {"file_stem": "chapter_content", "required_params": ("chapter", "engine")},
}
```

### 2. `novelbase/utils/registry.py`（修改）

- 删除 `FUNC_FILE_MAP`
- `capabilities()`：迭代 `CAPABILITY_META` 取 `meta["file_stem"]`
- `resolve()`：
  - 查 `CAPABILITY_META[function]` 取 `file_stem`（未知能力抛 `ValueError`）
  - 返回前 `inspect.signature(fn)` 校验 `required_params` 全部在参数列表中，缺失抛 `ValueError` 含模块路径与缺失参数名

### 3. `tests/test_source_contracts.py`（新建）

- 伪造缺参数函数 → resolve 被拒绝且报错含缺失参数名
- 遍历 CAPABILITY_META 对所有源的所有 mode 验证签名通过
- capabilities() 输出与改动前结构一致

## 测试

- `python -m pytest tests/ -v` — 现有 125 + 新增测试全绿
- 冒烟 `capabilities('fanqie')` / `resolve('fanqie','browser','search')` 输出不变

## 影响范围

| 文件 | 变更 |
|------|------|
| `novelbase/sources/contracts.py` | **新建** |
| `novelbase/utils/registry.py` | 删 FUNC_FILE_MAP，改 capabilities()/resolve() |
| `tests/test_source_contracts.py` | **新建** |

## 不做

- 不给 24 个 source 文件逐个加 `search: SearchFunc = search` 标注（无 mypy 时收益低）
- 不改 downloader.py 调用方式
- 不引入 mypy/pyright 为 dev 依赖
- 不硬编码源列表（新增源平台仅需创建目录+文件，零注册表修改）
