# 公开仓库准备执行计划

**日期**: 2026-08-13
**状态**: 已确认，待执行
**前置**: docs/ 已加入 .gitignore（不提交文档）

---

## 决策记录

| 决策点 | 结论 |
|--------|------|
| 公开仓库策略 | **新建公开仓库**（第一个 commit 即净化后文件树，历史零污染） |
| 书源公开范围 | **仅 fanqie 的 browser/requests/api(rain)** |
| 不公开书源 | fanqie api/oiapi、qidian、qimao、92xs（全部移出） |
| 文档是否公开 | 公开（净化后），私人仓库踩坑、公开仓库正式 |

---

## 一、书源公开清单

### 公开（进入公开仓库）

```
novelbase/sources/
├── __init__.py
├── contracts.py               # 能力契约（架构，干净）
└── fanqie/
    ├── __init__.py
    ├── _common.py             # 解析辅助（HTML 解析，干净）
    ├── browser/               # browser 模式 4 函数
    ├── requests/              # requests 模式 4 函数
    └── api/
        ├── __init__.py
        └── rain/              # Rain.ink 商业 API（apikey 参数公开，无逆向）
```

### 不公开（私人仓库保留，公开仓库删除）

```
novelbase/sources/fanqie/api/oiapi/   # 灰色逆向 API
novelbase/sources/qidian/             # 起点
novelbase/sources/qimao/              # 七猫
novelbase/sources/92xs/               # 就爱文学
```

## 二、连带修改（关键）

只删目录不够，必须同步这些文件，否则公开仓库仍暴露 oiapi/其他平台：

| 文件 | 现状 | 处理 |
|------|------|------|
| `novelbase/utils/_manifest.py` | 硬编码 4 平台 + oiapi/rain | 重新生成，只留 fanqie browser/requests/api(rain) |
| `novelbase/source.py` | NLD_PRIVATE_SOURCES 机制 | **保留**（公开仓库靠它加载用户私有源） |
| 后端/前端平台枚举 | 可能列出 4 平台 | 公开版只显示 fanqie |
| `tests/` 中的多平台测试 | 引用 qidian/qimao/92xs | 公开版移除或标记 skip |

### manifest 重新生成

```bash
# 公开仓库内，删掉其他平台目录后
python -m novelbase.tools.build_manifest
```

生成后 `_manifest.py` 只含 fanqie，且 modes 只有 `browser/requests/api(rain)`，无 oiapi。

## 三、文档净化

1. `docs/project/sources.md` + `updates.md`：改写"逆向/破解实现"→"第三方 API 变体"；书源表格只列 fanqie
2. `docs/superpowers/plans/` 旧计划：加 `> ⚠️ 已废弃` 标记（或直接不进公开仓库）
3. 敏感词扫描（已做）：无硬编码凭据，仅改措辞

## 四、公开仓库构造步骤

1. 私有仓库工作区 → 复制公开子集到临时目录
2. 删除不公开书源目录（oiapi/qidian/qimao/92xs）
3. 重新生成 manifest
4. 修改后端/前端平台枚举（仅 fanqie）
5. 敏感词扫描 + `pytest` 全绿验证
6. `git init` 新仓库，第一个 commit 推送公开子集
7. README 说明：其他平台/私有源走 `NLD_PRIVATE_SOURCES`

## 五、验证清单

- [ ] `git ls-files` 公开仓库无 oiapi/qidian/qimao/92xs
- [ ] `_manifest.py` 只含 fanqie browser/requests/api(rain)
- [ ] 无硬编码凭据（apikey 走 engine.options.key）
- [ ] `pytest` 全绿（fanqie 相关测试）
- [ ] docs 无"逆向/破解"字样

## 六、风险

| 风险 | 缓解 |
|------|------|
| 删除其他平台后测试失败 | 公开版移除/标记 skip 多平台测试 |
| rain 的 apikey 泄露格式被滥用 | Rain.ink 本身是公开商业服务，apikey 由用户自行申请，格式公开无风险 |
| manifest 忘重新生成导致残留 | 验证清单第 2 条硬性检查 |
| 前端平台枚举残留 | 验证清单 grep 平台名 |
