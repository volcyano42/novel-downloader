import {useCallback, useEffect, useMemo, useState} from "react";
import {Bell, ChevronDown, Gauge, Globe, Layers, Monitor, Package, Settings, Zap} from "lucide-react";
import {cn} from "@/lib/utils";
import {
    useFormatConfig,
    useSaveFormatConfig,
    useSaveGlobalConfig,
    useSaveSourceConfig,
    useSourceConfig,
    useSources
} from "@/hooks/index";
import {useToast} from "@/components/toast-context";
import type {GlobalConfig} from "@/api/endpoints";

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

function Range({ value, onChange, min, max, left, right }: { value: number; onChange: (v: number) => void; min: number; max: number; left: string; right: string }) {
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

function Section({ icon: Icon, title, children }: { icon: typeof Settings; title: string; children: React.ReactNode }) {
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

const MODE_META: Record<string, { label: string; icon: typeof Settings; desc: string }> = {
  browser: { label: "Browser", icon: Monitor, desc: "模拟浏览器，最稳定" },
  requests: { label: "Requests", icon: Globe, desc: "直接 HTTP，最快" },
  api: { label: "API", icon: Zap, desc: "第三方接口" },
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

/** 按书源编辑配置：选书源 → 逐能力段（cap → mode）渲染表单，落 `/config/sources/{name}`。 */
function SourceSection() {
  const { data: sources } = useSources();
  const sourceNames = useMemo(() => (sources ? Object.keys(sources) : []), [sources]);
  const [source, setSource] = useState("");
  const [open, setOpen] = useState(true);

  // 数据变化后保证有合法选中：无选择或已失效时回退到第一项
  useEffect(() => {
    if (!source && sourceNames.length > 0) setSource(sourceNames[0]);
    else if (source && !sourceNames.includes(source)) setSource(sourceNames[0] ?? "");
  }, [sourceNames, source]);

  const { data: cfg } = useSourceConfig(source || undefined);
  const saveSource = useSaveSourceConfig(source);

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

  return (
    <Section icon={Layers} title="书源配置">
      <div className="flex flex-wrap gap-1.5 py-2.5">
        {sourceNames.map(name => (
          <button key={name} onClick={() => setSource(name)}
            className={cn(
              "rounded-lg border px-3 py-1.5 text-xs font-medium transition-all",
              source === name
                ? "border-indigo-300 bg-indigo-50 text-indigo-600 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-400"
                : "border-white/20 bg-white/50 text-slate-500 hover:border-slate-200 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-400",
            )}>
            {name}
          </button>
        ))}
        {sourceNames.length === 0 && <span className="py-2 text-xs text-slate-400">暂无书源</span>}
      </div>
      {cfg && (
        <div>
          <Row label="启用" desc="关闭后不参与并发搜索">
            <Toggle checked={cfg.enabled} onChange={v => saveSource.mutate({ enabled: v })} />
          </Row>
          <button onClick={() => setOpen(!open)} className="flex items-center gap-1.5 w-full py-2 text-xs font-medium text-slate-500 hover:text-slate-700 transition-colors dark:text-slate-400 dark:hover:text-slate-300">
            <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${open ? "" : "-rotate-90"}`} strokeWidth={1.5} />
            {source} · 能力配置
          </button>
          {open && Object.entries(caps).map(([cap, mode]) => {
            const fields = ENGINE_FIELDS[mode] ?? [];
            const meta = MODE_META[mode];
            return (
              <div key={cap} className="border-t border-slate-100 dark:border-slate-800/50 pt-2 mt-2">
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
      )}
    </Section>
  );
}

const FORMAT_TABS = [
  { id: "txt", label: "TXT" },
  { id: "epub", label: "EPUB" },
  { id: "img", label: "IMG" },
] as const;

function FormatsSection() {
  const [tab, setTab] = useState("txt");
  const { data: fmtCfg } = useFormatConfig(tab);
  const saveFmt = useSaveFormatConfig(tab);

  return (
    <Section icon={Package} title="导出格式">
      <div className="flex gap-1.5 py-2.5">
        {FORMAT_TABS.map(({ id, label }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium uppercase transition-all ${tab === id ? "border-indigo-300 bg-indigo-50 text-indigo-600 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-400" : "border-white/20 bg-white/50 text-slate-500 hover:border-slate-200 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-400"}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === "txt" && (
        <Row label="编码">
          <Select value={String(fmtCfg?.encoding ?? "utf-8")} onChange={v => saveFmt.mutate({ ...fmtCfg, encoding: v })}
            options={[{ value: "utf-8", label: "UTF-8" }, { value: "gbk", label: "GBK" }]} />
        </Row>
      )}
      {tab === "epub" && (
        <>
          <Row label="压缩算法">
            <Select value={String(fmtCfg?.compression ?? "deflate")} onChange={v => saveFmt.mutate({ ...fmtCfg, compression: v })}
              options={[{ value: "deflate", label: "Deflate" }, { value: "bzip2", label: "BZip2" }, { value: "stored", label: "Stored" }]} />
          </Row>
          <Row label="压缩级别"><Num value={Number(fmtCfg?.compresslevel) || 9} onChange={v => saveFmt.mutate({ ...fmtCfg, compresslevel: v })} min={1} max={9} /></Row>
          <Row label="优化图片"><Toggle checked={!!fmtCfg?.optimize_images} onChange={v => saveFmt.mutate({ ...fmtCfg, optimize_images: v })} /></Row>
          <Row label="JPEG 质量"><Num value={Number(fmtCfg?.jpeg_quality) || 85} onChange={v => saveFmt.mutate({ ...fmtCfg, jpeg_quality: v })} min={1} max={100} /></Row>
          <Row label="最大图宽"><Num value={Number(fmtCfg?.max_image_width) || 0} onChange={v => saveFmt.mutate({ ...fmtCfg, max_image_width: v })} min={0} max={4096} unit="px" /></Row>
          <Row label="包含目录"><Toggle checked={!!fmtCfg?.include_toc} onChange={v => saveFmt.mutate({ ...fmtCfg, include_toc: v })} /></Row>
        </>
      )}
      {tab === "img" && (
        <Row label="输出格式">
          <Select value={String(fmtCfg?.output_format ?? "original")} onChange={v => saveFmt.mutate({ ...fmtCfg, output_format: v })}
            options={[{ value: "original", label: "原始" }, { value: "jpeg", label: "JPEG" }, { value: "png", label: "PNG" }, { value: "webp", label: "WebP" }]} />
        </Row>
      )}
    </Section>
  );
}

interface SettingsViewProps {
  globalConfig: GlobalConfig;
  onUpdate: (path: string, value: unknown) => void;
}

export function SettingsView({ globalConfig, onUpdate }: SettingsViewProps) {
  const saveGlobal = useSaveGlobalConfig();
  const toast = useToast();

  const updateGlobal = useCallback((key: string, value: unknown) => {
    saveGlobal.mutateAsync({ ...globalConfig, [key]: value })
      .then(() => toast("设置已保存", "success"))
      .catch(() => toast("设置保存失败", "error"));
    onUpdate(key, value);
  }, [globalConfig, saveGlobal, onUpdate, toast]);

  return (
    <div className="mx-auto max-w-[640px] space-y-4">
      <SourceSection />

      <Section icon={Gauge} title="并发与性能">
        <Row label="并发线程数" desc="同时下载的章节数">
          <Range value={globalConfig.max_workers} onChange={v => updateGlobal("max_workers", v)} min={1} max={10} left="1" right="10" />
        </Row>
        <Row label="提示" desc="💡 建议 3-5，Browser 模式建议 1-3，过高触发反爬拦截"><span /></Row>
      </Section>

      <FormatsSection />

      <Section icon={Bell} title="通知">
        <Row label="下载完成时" desc="全部章节下载成功时触发">
          <Toggle checked={globalConfig.notify?.on_complete ?? true} onChange={v => updateGlobal("notify", { ...globalConfig.notify, on_complete: v })} />
        </Row>
        <Row label="有不完整章节时" desc="部分章节失败或缺失时触发">
          <Toggle checked={globalConfig.notify?.on_incomplete ?? true} onChange={v => updateGlobal("notify", { ...globalConfig.notify, on_incomplete: v })} />
        </Row>
        <Row label="提示音" desc="bell=终端响铃, system=系统通知, none=静默">
          <Select value={globalConfig.notify?.sound ?? "bell"} onChange={v => updateGlobal("notify", { ...globalConfig.notify, sound: v })}
            options={[{ value: "bell", label: "🔔 响铃" }, { value: "system", label: "💻 系统通知" }, { value: "none", label: "🔇 静默" }]} />
        </Row>
      </Section>
    </div>
  );
}
