/** 书源配置表单的共享实现：UI 原子 + 能力字段元数据 + 逐能力段编辑器。
 *
 * 唯一来源——`SourceAccordion`（设置页折叠条）与 `SettingsPage`（设置页书源段）都从这里 import，
 * 避免两份逐字重复的实现漂移。
 */
import {useEffect, useState} from "react";
import type {LucideIcon} from "lucide-react";
import {useEnvironment, useSaveSourceConfig, useSourceConfig} from "@/hooks/index";
import {cn} from "@/lib/utils";
import {CAP_LABELS, ENGINE_FIELDS, MODE_META} from "./sourceConfigFields";
import type {EngineField} from "./sourceConfigFields";

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

export function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button onClick={() => onChange(!checked)} disabled={disabled}
      className={`relative h-5 w-9 rounded-full transition-colors duration-200 ${disabled ? "cursor-not-allowed opacity-40" : ""} ${checked ? "bg-indigo-500" : "bg-slate-300 dark:bg-slate-600"}`}>
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

/** JSON 对象字段（如 headers）：文本域编辑，失焦时解析；非法则提示且不写回。 */
export function JsonField({ value, onCommit }: { value: unknown; onCommit: (v: Record<string, unknown>) => void }) {
  const toText = (v: unknown) => JSON.stringify(v ?? {}, null, 2);
  const [text, setText] = useState(() => toText(value));
  const [error, setError] = useState(false);

  // 服务端值变化（保存后 refetch）时同步文本
  useEffect(() => { setText(toText(value)); setError(false); }, [value]);

  const commit = () => {
    const raw = text.trim();
    if (!raw) { setError(false); onCommit({}); return; }
    try {
      const parsed: unknown = JSON.parse(raw);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        setError(false);
        onCommit(parsed as Record<string, unknown>);
      } else {
        setError(true);
      }
    } catch {
      setError(true);
    }
  };

  return (
    <div className="w-full">
      <textarea value={text} onChange={e => setText(e.target.value)} onBlur={commit} rows={4} spellCheck={false}
        className={cn("w-full rounded-lg border bg-white/50 px-2 py-1.5 font-mono text-xs text-slate-700 outline-none backdrop-blur-sm dark:bg-slate-800/50 dark:text-slate-300",
          error ? "border-red-300 dark:border-red-500/40" : "border-white/20 dark:border-slate-600/30")} />
      {error && <p className="mt-1 text-[11px] text-red-400">JSON 格式错误，未保存</p>}
    </div>
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

/** 单个书源的逐能力段配置编辑器（数据走 useSourceConfig，写走 useSaveSourceConfig）。 */
export function SourceConfigEditor({ name }: { name: string }) {
  const { data: cfg } = useSourceConfig(name);
  const saveSource = useSaveSourceConfig(name);
  const { data: env } = useEnvironment();

  const caps = cfg?.capabilities ?? {};
  const declared = cfg?.declared_capabilities ?? {};
  const merged = cfg?.config ?? {};
  // mode 下拉只列**本环境支持**的选项（Android 下没有 browser）；env 未就绪时退回全量，避免闪动
  const supported = env?.supported_modes;
  const modeOptions = Object.entries(MODE_META)
    .filter(([m]) => !supported || supported.includes(m))
    .map(([m, meta]) => ({ value: m, label: meta.label }));

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
      case "json":
        return <JsonField value={val} onCommit={v => set(v)} />;
      case "text":
        return <TextField value={String(val ?? "")} onChange={v => set(v)} />;
      case "range-delay":
        return (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <input type="number" value={(val as number[])?.[0] ?? 0} onChange={e => set([Number(e.target.value), (val as number[])?.[1] ?? 0])} min={f.min} max={f.max}
              className="w-14 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
            <span>~</span>
            <input type="number" value={(val as number[])?.[1] ?? 0} onChange={e => set([(val as number[])?.[0] ?? 0, Number(e.target.value)])} min={f.min} max={f.max}
              className="w-14 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
            <span className="text-[11px] text-slate-400">{f.unit}</span>
          </div>
        );
    }
  };

  if (!cfg) return <div className="py-2 text-xs text-slate-400">加载中…</div>;

  return (
    <div className="border-t border-slate-100 pt-2 pb-1 dark:border-slate-800/50">
      <p className="pb-1 text-[11px] text-slate-400">
        切换引擎模式可能不可用（不同模式的接口/参数互不通用）；不可用时点「恢复默认」回退。
      </p>
      {Object.entries(caps).length === 0 && <p className="py-1 text-[11px] text-slate-400">该书源未声明能力</p>}
      {Object.entries(caps).map(([cap, mode]) => {
        const fields = ENGINE_FIELDS[mode] ?? [];
        return (
          <div key={cap} className="border-t border-slate-100 first:border-t-0 dark:border-slate-800/50">
            <div className="flex flex-wrap items-center gap-2 py-1">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-300">{CAP_LABELS[cap] ?? cap}</span>
              <Select value={mode}
                onChange={v => saveSource.mutate({ config: { [cap]: { mode: v } } })}
                // 当前 mode 若不在受支持列表（env 未就绪或历史覆盖），仍补进选项，避免下拉空白
                options={modeOptions.some(o => o.value === mode)
                  ? modeOptions
                  : [...modeOptions, { value: mode, label: MODE_META[mode]?.label ?? mode }]} />
              {declared[cap] && declared[cap] !== mode && (
                <button onClick={() => saveSource.mutate({ config: { [cap]: { mode: null } } })}
                  className="text-[10px] font-medium text-indigo-500 hover:underline">
                  恢复默认（{declared[cap]}）
                </button>
              )}
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
