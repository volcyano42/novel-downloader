/** 书源配置表单的字段元数据（非组件常量，与 sourceConfigForm.tsx 分离，
 * 避免 `react(only-export-components)` Fast-Refresh 警告）。
 *
 * 唯一来源——`sourceConfigForm.tsx`（编辑器实现）/ `SourceAccordion.tsx`（折叠条）/ `SourcesPage.tsx` 都从这里取。
 */
import type {LucideIcon} from "lucide-react";
import {Globe, Monitor, Zap} from "lucide-react";

export const MODE_META: Record<string, { label: string; icon: LucideIcon; desc: string }> = {
  browser: { label: "Browser", icon: Monitor, desc: "模拟浏览器，最稳定" },
  requests: { label: "Requests", icon: Globe, desc: "直接 HTTP，最快" },
  api: { label: "API", icon: Zap, desc: "第三方接口" },
};

export const CAP_LABELS: Record<string, string> = {
  search: "搜索",
  novel_info: "书籍信息",
  chapter_list: "章节列表",
  chapter_content: "章节内容",
};

export type EngineField = {
  label: string; desc?: string;
  type: "toggle" | "num" | "select" | "range-delay" | "text" | "json";
  key: string;
  opts?: { value: string; label: string }[];
  min?: number; max?: number; unit?: string;
};

export const ENGINE_FIELDS: Record<string, EngineField[]> = {
  browser: [
    { key: "headless", label: "无头模式", desc: "后台静默运行，不弹窗口", type: "toggle" },
    { key: "browser_type", label: "浏览器类型", type: "select", opts: [{ value: "chromium", label: "Chromium" }, { value: "firefox", label: "Firefox" }, { value: "webkit", label: "WebKit" }] },
    { key: "user_data_dir", label: "用户数据目录", desc: "保存登录态和缓存", type: "text" },
    { key: "delay", label: "请求延迟", desc: "两章之间随机等待", type: "range-delay", min: 0, max: 30, unit: "秒" },
    { key: "timeout", label: "超时", desc: "单次请求最长等待", type: "num", min: 5, max: 120, unit: "秒" },
    { key: "retry_times", label: "重试次数", type: "num", min: 0, max: 10 },
    { key: "backoff_factor", label: "退避因子", desc: "重试间隔倍增系数", type: "num", min: 1, max: 10 },
  ],
  requests: [
    { key: "headers", label: "请求头", desc: "JSON 对象，如 {\"Cookie\": \"…\"}", type: "json" },
    { key: "delay", label: "请求延迟", desc: "两章之间随机等待", type: "range-delay", min: 0, max: 30, unit: "秒" },
    { key: "timeout", label: "超时", desc: "单次请求最长等待", type: "num", min: 5, max: 120, unit: "秒" },
    { key: "retry_times", label: "重试次数", type: "num", min: 0, max: 10 },
    { key: "backoff_factor", label: "退避因子", desc: "重试间隔倍增系数", type: "num", min: 1, max: 10 },
  ],
  api: [
    { key: "key", label: "API Key", type: "text" },
    { key: "delay", label: "请求延迟", desc: "两章之间随机等待", type: "range-delay", min: 0, max: 30, unit: "秒" },
    { key: "timeout", label: "超时", desc: "单次请求最长等待", type: "num", min: 5, max: 120, unit: "秒" },
    { key: "retry_times", label: "重试次数", type: "num", min: 0, max: 10 },
    { key: "backoff_factor", label: "退避因子", desc: "重试间隔倍增系数", type: "num", min: 1, max: 10 },
  ],
};

/** 「常规」段字段：各能力段 mode 的**共有字段**（不含 `mode` 自身）。
 *
 * 4 段都是 api → 含 key/params/delay/timeout/retry_times/backoff_factor；
 * 某段改成 requests → 交集自动收窄（`key` 从常规段消失，只留在 api 那个能力段）。
 * 字段顺序与元数据取自首个 mode，保证展示稳定。 */
export function commonFieldsFor(modes: string[]): EngineField[] {
  if (modes.length === 0) return [];
  const lists = modes.map(m => ENGINE_FIELDS[m] ?? []);
  const [first, ...rest] = lists;
  return first.filter(
    f => f.key !== "mode" && rest.every(list => list.some(g => g.key === f.key)),
  );
}
