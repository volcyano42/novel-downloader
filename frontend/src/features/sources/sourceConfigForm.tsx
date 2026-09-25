/** 书源配置表单的共享实现：UI 原子 + 能力字段元数据 + 逐能力段编辑器。
 *
 * 唯一来源——`SourcesPage`（书源管理页）与 `SettingsPage`（设置页书源段）都从这里 import，
 * 避免两份逐字重复的实现漂移。
 */
import {useEffect, useState} from "react";
import type {LucideIcon} from "lucide-react";
import {Globe, Monitor, Zap} from "lucide-react";
import {useSaveSourceConfig, useSourceConfig} from "@/hooks/index";

export function Row({ label, desc, children }: { label: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-xs font-medium text-slate-700 dark:text-slate-300">{label}</span>
        {desc && <span className="text-[11px] text-slate-400 dark:text-slate-500">{desc}</span>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)}
      className={`relative h-5 w-9 rounded-full transition-colors duration-200 ${checked ? "bg-indigo-500" : "bg-slate-300 dark:bg-slate-600"}`}>
      <span className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-all duration-200 ${checked ? "translate-x-4" : "translate-x-0"}`} />
    </button>
  );
}

export function Select({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2.5 py-1.5 text-xs text-slate-700 outline-none appearance-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30">
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function Num({ value, onChange, min, max, step = 1, unit }: { value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; unit?: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <input type="number" value={value} onChange={e => onChange(Number(e.target.value))} min={min} max={max} step={step}
        className="w-16 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
      {unit && <span className="text-[11px] text-slate-400">{unit}</span>}
    </div>
  );
}

export function TextField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [local, setLocal] = useState(value);
  useEffect(() => { setLocal(value); }, [value]);
  return (
    <input type="text" value={local} onChange={e => setLocal(e.target.value)}
      onBlur={() => { if (local !== value) onChange(local); }}
      onKeyDown={e => { if (e.key === "Enter") { if (local !== value) onChange(local); (e.target as HTMLInputElement).blur(); } }}
      className="w-40 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2.5 py-1.5 text-xs text-slate-700 outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
  );
}

export function Range({ value, onChange, min, max, left, right }: { value: number; onChange: (v: number) => void; min: number; max: number; left: string; right: string }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div className="flex flex-col gap-0.5 w-full max-w-[200px] group">
      <div className="relative h-4">
        <span className="absolute text-[11px] font-semibold text-indigo-500 tabular-nums -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity" style={{ left: `${pct}%` }}>{value}</span>
      </div>
      <input type="range" min={min} max={max} value={value} onChange={e => onChange(Number(e.target.value))}
        className="w-full h-8 appearance-none bg-transparent cursor-pointer
          [&::-webkit-slider-runnable-track]:h-1.5 [&::-webkit-slider-runnable-track]:rounded-full [&::-webkit-slider-runnable-track]:bg-slate-200 dark:[&::-webkit-slider-runnable-track]:bg-slate-700
          [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-indigo-500 [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:-mt-[5px]" />
      <div className="flex justify-between text-[10px] text-slate-400">
        <span>{left}</span>
        <span>{right}</span>
      </div>
    </div>
  );
}

export function Section({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-white/20 bg-white/80 backdrop-blur-xl shadow-card overflow-hidden dark:bg-slate-900/80 dark:border-slate-700/30">
      <div className="flex items-center gap-2.5 border-b border-white/10 px-5 py-3 dark:border-slate-700/30">
        <Icon className="h-4 w-4 text-indigo-500" strokeWidth={1.5} />
        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">{title}</h3>
      </div>
      <div className="px-5 py-2 divide-y divide-slate-100 dark:divide-slate-800/50">{children}</div>
    </section>
  );
}

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
  type: "toggle" | "num" | "select" | "range-delay" | "text";
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
    { key: "headers", label: "请求头", desc: "JSON 格式，如 {\"Cookie\": \"…\"}", type: "text" },
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

/** 单个书源的逐能力段配置编辑器（数据走 useSourceConfig，写走 useSaveSourceConfig）。 */
export function SourceConfigEditor({ name }: { name: string }) {
  const { data: cfg } = useSourceConfig(name);
  const saveSource = useSaveSourceConfig(name);

  const caps = cfg?.capabilities ?? {};
  const merged = cfg?.config ?? {};

  const updateField = (cap: string, key: string, value: unknown) => {
    saveSource.mutate({ config: { [cap]: { [key]: value } } });
  };

  const renderField = (cap: string, f: EngineField) => {
    const val = (merged[cap] as unknown as Record<string, unknown> | undefined)?.[f.key];
    const set = (value: unknown) => updateField(cap, f.key, value);
    switch (f.type) {
      case "toggle":
        return <Toggle checked={!!val} onChange={v => set(v)} />;
      case "select":
        return <Select value={String(val ?? f.opts![0].value)} onChange={v => set(v)} options={f.opts!} />;
      case "num":
        return <Num value={Number(val) || 0} onChange={v => set(v)} min={f.min} max={f.max} unit={f.unit} />;
      case "text":
        return <TextField value={String(val ?? "")} onChange={v => set(v)} />;
      case "range-delay":
        return (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <input type="number" value={(val as number[])?.[0] ?? 3} onChange={e => set([Number(e.target.value), (val as number[])?.[1] ?? 5])} min={f.min} max={f.max}
              className="w-14 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
            <span>~</span>
            <input type="number" value={(val as number[])?.[1] ?? 5} onChange={e => set([(val as number[])?.[0] ?? 3, Number(e.target.value)])} min={f.min} max={f.max}
              className="w-14 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
            <span className="text-[11px] text-slate-400">{f.unit}</span>
          </div>
        );
    }
  };

  if (!cfg) return <div className="py-2 text-xs text-slate-400">加载中…</div>;

  return (
    <div className="border-t border-slate-100 pt-2 pb-1 dark:border-slate-800/50">
      {Object.entries(caps).length === 0 && <p className="py-1 text-[11px] text-slate-400">该书源未声明能力</p>}
      {Object.entries(caps).map(([cap, mode]) => {
        const fields = ENGINE_FIELDS[mode] ?? [];
        const meta = MODE_META[mode];
        return (
          <div key={cap} className="border-t border-slate-100 first:border-t-0 dark:border-slate-800/50">
            <div className="flex items-center gap-2 py-1">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-300">{CAP_LABELS[cap] ?? cap}</span>
              {meta && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">{meta.label}</span>}
            </div>
            {fields.length === 0
              ? <p className="py-1 text-[11px] text-slate-400">该能力无可配置项</p>
              : fields.map(f => <Row key={f.key} label={f.label} desc={f.desc}>{renderField(cap, f)}</Row>)}
          </div>
        );
      })}
    </div>
  );
}
