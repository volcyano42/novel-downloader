import {useEffect, useMemo, useState} from "react";
import {useQueryClient} from "@tanstack/react-query";
import {ChevronDown, Globe, Layers, Monitor, Zap} from "lucide-react";
import {cn} from "@/lib/utils";
import {useSaveSourceConfig, useSourceConfig, useSources} from "@/hooks/index";

// ── 展示小组件（与 features/settings/SettingsPage.tsx 同风格）──────

function Row({ label, desc, children }: { label: string; desc?: string; children: React.ReactNode }) {
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

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)}
      className={`relative h-5 w-9 rounded-full transition-colors duration-200 ${checked ? "bg-indigo-500" : "bg-slate-300 dark:bg-slate-600"}`}>
      <span className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-all duration-200 ${checked ? "translate-x-4" : "translate-x-0"}`} />
    </button>
  );
}

function Select({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2.5 py-1.5 text-xs text-slate-700 outline-none appearance-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30">
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

function Num({ value, onChange, min, max, step = 1, unit }: { value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; unit?: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <input type="number" value={value} onChange={e => onChange(Number(e.target.value))} min={min} max={max} step={step}
        className="w-16 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
      {unit && <span className="text-[11px] text-slate-400">{unit}</span>}
    </div>
  );
}

function TextField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [local, setLocal] = useState(value);
  useEffect(() => { setLocal(value); }, [value]);
  return (
    <input type="text" value={local} onChange={e => setLocal(e.target.value)}
      onBlur={() => { if (local !== value) onChange(local); }}
      onKeyDown={e => { if (e.key === "Enter") { if (local !== value) onChange(local); (e.target as HTMLInputElement).blur(); } }}
      className="w-40 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2.5 py-1.5 text-xs text-slate-700 outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
  );
}

function Section({ icon: Icon, title, children }: { icon: typeof Layers; title: string; children: React.ReactNode }) {
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

const MODE_META: Record<string, { label: string; icon: typeof Layers }> = {
  browser: { label: "Browser", icon: Monitor },
  requests: { label: "Requests", icon: Globe },
  api: { label: "API", icon: Zap },
};

const CAP_LABELS: Record<string, string> = {
  search: "搜索",
  novel_info: "书籍信息",
  chapter_list: "章节列表",
  chapter_content: "章节内容",
};

type EngineField = {
  label: string; desc?: string;
  type: "toggle" | "num" | "select" | "range-delay" | "text";
  key: string;
  opts?: { value: string; label: string }[];
  min?: number; max?: number; unit?: string;
};

const ENGINE_FIELDS: Record<string, EngineField[]> = {
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

/** 单个书源的逐能力段配置编辑器，展开时才挂载（数据走 useSourceConfig，写走 useSaveSourceConfig）。 */
function SourceConfigEditor({ name }: { name: string }) {
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

/** 列表单行：书源名 + 能力摘要 + enabled 开关 + 编辑配置入口。 */
function SourceRow({ name, info }: { name: string; info: { capabilities: Record<string, string>; enabled: boolean } }) {
  const qc = useQueryClient();
  const saveSource = useSaveSourceConfig(name);
  const [enabled, setEnabled] = useState(info.enabled);
  const [open, setOpen] = useState(false);

  // 列表数据（useSources）刷新后同步开关显示
  useEffect(() => { setEnabled(info.enabled); }, [info.enabled]);

  const caps = info.capabilities ?? {};

  const toggleEnabled = (v: boolean) => {
    setEnabled(v); // 乐观更新，避免受控开关因 refetch 滞后回弹
    saveSource.mutate({ enabled: v }, {
      onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
    });
  };

  return (
    <div className="py-1">
      <div className="flex items-center justify-between gap-4 py-1.5">
        <div className="min-w-0">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{name}</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {Object.keys(caps).length === 0 && <span className="text-[11px] text-slate-400">无能力</span>}
            {Object.entries(caps).map(([cap, mode]) => (
              <span key={cap} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {CAP_LABELS[cap] ?? cap}·{mode}
              </span>
            ))}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Toggle checked={enabled} onChange={toggleEnabled} />
          <button onClick={() => setOpen(o => !o)}
            className="flex items-center gap-1 text-xs font-medium text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-200", open && "rotate-180")} strokeWidth={1.5} />
            编辑配置
          </button>
        </div>
      </div>
      {open && <SourceConfigEditor name={name} />}
    </div>
  );
}

export default function SourcesPage() {
  const { data: sources } = useSources();
  const names = useMemo(() => (sources ? Object.keys(sources) : []), [sources]);

  return (
    <div className="px-6 pt-12 pb-8 md:px-12">
      <div className="mx-auto max-w-[720px] space-y-4">
        <Section icon={Layers} title="书源管理">
          {names.map(name => (
            <SourceRow key={name} name={name} info={sources![name]} />
          ))}
          {names.length === 0 && <div className="py-3 text-xs text-slate-400">暂无书源</div>}
        </Section>
      </div>
    </div>
  );
}
