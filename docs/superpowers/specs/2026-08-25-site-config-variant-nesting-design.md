# sites 配置嵌套 variant 层（browser/requests 加 default）设计

日期：2026-08-25
状态：已获用户批准（含两个决策：variant 感知读取、只支持新格式）

## 背景

书源代码已按 `{mode}/{variant}/` 组织（`fanqie/browser/default/`、`requests/default/`、`api/{oiapi,rain,appapi}/`），
`source.resolve()` 与 capabilities 统一为 `{mode: {variant: [functions]}}` 结构（commit `ee5391a`，2026-08-22）。
前端搜索/下载的 variant 选择（`modeVariants`）从 sources capabilities 派生（commit `b42747b`），
browser/requests 的 default variant 已在前端搜索/下载流程生效。

但**配置文件与配置读取代码未跟上**：`sites/{platform}.yaml` 的 `browser`/`requests` 仍是扁平 mode 级
（仅 `api` 是 variant 层级），7 处配置读取代码（shared/cli/backend/前端）都假设扁平结构。

本设计把配置文件嵌套一层 variant（当前唯一为 `default`），并让所有配置读取方变为 variant 感知。

## 决策（用户确认）

1. **读取语义**：variant 感知读取——variant 缺省时优先 `default`，否则取第一个可用 variant（与 `source.resolve` 语义对齐）。
2. **旧配置兼容**：只支持新格式。已存在的扁平 `app_data/config/sites/*.yaml` 需手动删除，由 `init_config` 重新生成。
3. **实现方式**：抽公共辅助函数（数据访问层），消费方统一改用，避免 7 处逻辑重复。

## 配置文件格式（新）

`sites/{platform}.yaml`：

```yaml
browser:
  default:            # ← 新增 variant 层（唯一 variant）
    backoff_factor: 2
    browser_type: chromium
    delay: [2, 5]
    headless: false
    ...
requests:
  default:            # ← 新增 variant 层
    backoff_factor: 2
    cookies: {}
    ...
api:                  # 不变（已是 variant 层级）
  oiapi: {...}
  rain: {...}
```

涉及文件（template 与 app_data 各 4 个）：`sites/{fanqie,qidian,qimao,92xs}.yaml`。

## 数据访问层（shared/config.py）

新增：

```python
def get_mode_variant_config(site_cfg, mode, variant=None) -> dict:
    """site_cfg[mode][variant]；variant=None → 优先 default → 否则第一个 dict 值。"""

def load_mode_config(platform, mode, variant=None) -> dict:
    """load_site_config + get_mode_variant_config（含 app_data 路径解析）。"""

def mode_variants(site_cfg, mode) -> list[str]:
    """某 mode 下的 variant 列表（dict 键，过滤非 dict 值）。"""
```

修改：

- `find_variant_options(variant)`：扩展为跨 mode 查找（api → browser → requests），供 engine_manager API 分支继续使用
- `load_platform_configs()` / `build_options()`（后者现无调用者，遗留）：改用辅助函数保持一致

## 消费方适配

| 文件 | 改动 |
|------|------|
| `cli/config.py` `build_options()` | browser/requests 用 `get_mode_variant_config(site_cfg, mode)`（None → default）；api 不变 |
| `backend/services/engine_manager.py` | `_fingerprint()` 与 `create_engine_for_request()` 的 `mode_cfg = site.get(mode, {})` → `get_mode_variant_config(site, mode, variant)`；API 分支不变 |
| `cli/menus.py` | `_settings_site_browser/requests` 操作 `site_cfg.setdefault(mode, {}).setdefault("default", {})`；`_get_delay`/`_set_delay` 取/写 `.get(mode, {}).get("default", {})` |
| `backend/routers/config.py` | `get_site()` 返回嵌套结构（browser/requests 为 `{default: 合并 ENGINE_DEFAULTS 后的配置}`）；`save_site()` 对嵌套结构 deep_merge（递归天然支持），过滤非 dict variant |

## 前端适配（最小）

- `frontend/src/api/endpoints.ts`：`SiteConfig.browser/requests` 类型改为 variant 容器 `Record<string, EngineOptions>`
- `frontend/src/features/settings/SettingsPage.tsx`：
  - browser/requests 读取 `siteCfg[mode].default`（`engineCfg`）
  - 保存 `{ [mode]: { default: {...} } }`（`updateField`）
  - api 逻辑不动（`ApiVariantsSection` 不变）

## 测试

- `tests/test_interactive_cli.py`：`_get_delay` 断言数据改嵌套 `{"browser": {"default": {"delay": [1, 2]}}}`
- 新增 `get_mode_variant_config` 单测：None→default、指定 variant、无 default 取第一个、非 dict 值过滤
- `tests/test_engine_manager.py`：依赖实际配置，app_data 更新为新格式后应通过

## 数据迁移

- `app_data/config/sites/*.yaml` 同步新格式（本地运行/测试用，不进 git）
- 老格式用户配置：手动删除后由 `init_config` 重新生成（按决策只支持新格式）

## 文档

- 根 `docs/project/config.md` 同步 site 配置结构说明（若涉及）

## 明确不做

- 前端 variant 切换 UI（YAGNI：default 唯一时表单照旧；前端搜索/下载的 variant 选择已基于 capabilities 工作，不依赖配置）
- 旧格式兼容读取（按决策只支持新格式）
- shared/config.py `load_platform_configs()`/`build_options()` 的调用方新增（现无调用者，仅保持一致性更新）
