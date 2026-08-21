# Novel.origin_id 派生属性设计

2026-08-02

## 概述

给 `Novel` 模型添加只读派生属性 `origin_id`，值为 `Novel.id` 去掉 `{website}_` 前缀后的源站原始 ID。

## 动机

各平台 `Novel.id` 统一带平台前缀（如 `fanqie_7123456789012345678`），而源站接口/URL 需要的是原始数字 ID（如 `7123456789012345678`）。当前各平台在需要原始 ID 的地方各自调用 `standardize_id()` 处理，缺少统一访问入口。

## 各平台 id 格式

| 平台 | Novel.id 格式 | 期望 origin_id |
|------|--------------|----------------|
| fanqie | `fanqie_{19位数字}` | `{19位数字}` |
| qidian | `qidian_{10位数字}` | `{10位数字}` |
| qimao | `qimao_{数字}` | `{数字}` |
| 92xs | `92xs_{数字}` | `{数字}` |

## 设计决策

| 决策 | 结论 | 理由 |
|------|------|------|
| 实现方式 | `@property` 派生 | 用户选定；零构造点改动，任何来源恢复的 Novel 均能现算取值 |
| 前缀剥离规则 | `id.split("_", 1)[1]` | 4 平台前缀均含 `_`，通用；id 不含 `_` 时原样返回（防御异常数据） |
| 序列化 | 不持久化 | property 不参与 `asdict`/JSON 序列化，属派生值而非存储字段 |
| loads() 兼容性 | no-op setter | `Novel.loads` 对未知 kwargs 做 `setattr`，需避免未来数据含 `origin_id` 键时抛 `AttributeError` |

## 实现

仅修改 `novelbase/models/novel.py` 的 `Novel` dataclass：

```python
@property
def origin_id(self) -> str:
    """源站原始 ID：Novel.id 去掉 {website}_ 前缀（如 fanqie_7123... → 7123...）。"""
    if self.id and "_" in self.id:
        return self.id.split("_", 1)[1]
    return self.id

@origin_id.setter
def origin_id(self, value) -> None:
    """只读属性，忽略赋值（兼容 Novel.loads 的 setattr 流程）。"""
    pass
```

## 测试

`tests/test_models.py` 的 `TestNovel` 新增：

1. 4 平台 id 格式派生正确（`fanqie_`/`qidian_`/`qimao_`/`92xs_` 前缀剥离）
2. id 不含 `_` 时原样返回
3. `Novel.loads(..., origin_id="...")` 传入该键不报错，且派生值不受影响

## 影响范围

- 核心库：`novelbase/models/novel.py`（仅 Novel）
- 测试：`tests/test_models.py`
- **无改动**：存储 schema、API schema、前端、各平台 source 构造点

## 不在范围内

- 不持久化 `origin_id` 到 SQLite / JSON 存储
- 不修改 `Novel.id` 本身
- 不修改 4 平台 `parse_novel_info` 构造逻辑
