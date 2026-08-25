import {useCallback, useEffect, useMemo, useState} from "react";
import {
    Bell,
    ChevronDown,
    Download,
    Eye,
    EyeOff,
    Gauge,
    Globe,
    Layers,
    Monitor,
    Package,
    Settings,
    Zap
} from "lucide-react";
import {cn} from "@/lib/utils";
import {
    useFormatConfig,
    usePlatforms,
    useSaveFormatConfig,
    useSaveGlobalConfig,
    useSaveSiteConfig,
    useSiteConfig,
    useSources
} from "@/hooks/index";
import {useToast} from "@/components/Toast";
import type {GlobalConfig, SiteConfig} from "@/api/endpoints";

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
const KNOWN_MODE_ORDER = ["browser", "requests", "api"] as const;

const ENGINE_FIELDS: Record<string, { label: string; desc?: string; type: "toggle" | "num" | "select" | "range-delay" | "text"; key: string; opts?: { value: string; label: string }[]; min?: number; max?: number; unit?: string }[]> = {
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
    { key: "delay", label: "请求延迟", desc: "两章之间随机等待", type: "range-delay", min: 0, max: 30, unit: "秒" },
    { key: "timeout", label: "超时", desc: "单次请求最长等待", type: "num", min: 5, max: 120, unit: "秒" },
    { key: "retry_times", label: "重试次数", type: "num", min: 0, max: 10 },
    { key: "backoff_factor", label: "退避因子", desc: "重试间隔倍增系数", type: "num", min: 1, max: 10 },
  ],
  api: [],
};

function EngineSection({ mode }: { mode: string }) {
  const { data: platforms = [] } = usePlatforms();
  const { data: sources } = useSources();
  // 只显示支持当前 mode 的平台（不支持的 mode 在 capabilities 中没有 key）
  const supported = useMemo(() => {
    if (!sources) return platforms;
    return platforms.filter(p => {
      const caps = sources[p.id]?.capabilities;
      return caps ? caps[mode] !== undefined : false;
    });
  }, [platforms, sources, mode]);

  const [platform, setPlatform] = useState<string>(supported[0]?.id ?? "fanqie");
  const [engineOpen, setEngineOpen] = useState(false);

  // mode 或数据变化后，若当前平台不支持该 mode，自动切到第一个支持的平台
  useEffect(() => {
    if (supported.length > 0 && !supported.some(p => p.id === platform)) {
      setPlatform(supported[0].id);
    }
  }, [supported, platform]);

  const { data: siteCfg } = useSiteConfig(platform);
  const saveSite = useSaveSiteConfig(platform);

  const rawModeCfg = (siteCfg?.[mode as keyof SiteConfig] as Record<string, unknown> | undefined) ?? {};
  // browser/requests 是 variant 容器，表单操作 default variant；api 保持 variant 容器原样
  const engineCfg = (mode === "api"
    ? rawModeCfg
    : ((rawModeCfg.default as Record<string, unknown> | undefined) ?? {}));
  const fields = ENGINE_FIELDS[mode] ?? [];
  // 优先用 siteCfg.api_variants（config 端点，含全部 variant 含 disabled）；
  // 远程访问/配置未初始化时 fallback 到 sources capabilities（enabled 的 api variant）
  const apiVariants: string[] = useMemo(() => {
    const fromSite = siteCfg?.api_variants ?? [];
    if (fromSite.length > 0) return fromSite;
    if (sources) {
      const caps = sources[platform]?.capabilities;
      if (caps?.api && typeof caps.api === "object" && !Array.isArray(caps.api)) {
        return Object.keys(caps.api).filter(k => k !== "");
      }
    }
    return [];
  }, [siteCfg, sources, platform]);
  const hasVariants = mode === "api" && apiVariants.length > 0;

  // 只服务 browser/requests 字段：保存到 default variant；api 走 ApiVariantsSection
  const updateField = useCallback((key: string, value: unknown) => {
    saveSite.mutate({ [mode]: { default: { [key]: value } } });
  }, [mode, saveSite]);

  const renderField = (f: typeof fields[number]) => {
    const val = engineCfg[f.key];
    switch (f.type) {
      case "toggle":
        return <Toggle checked={!!val} onChange={v => updateField(f.key, v)} />;
      case "select":
        return <Select value={String(val ?? f.opts![0].value)} onChange={v => updateField(f.key, v)} options={f.opts!} />;
      case "num":
        return <Num value={Number(val) || 0} onChange={v => updateField(f.key, v)} min={f.min} max={f.max} unit={f.unit} />;
      case "text":
        return <TextField value={String(val ?? "")} onChange={v => updateField(f.key, v)} />;
      case "range-delay":
        return (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <input type="number" value={(val as number[])?.[0] ?? 3} onChange={e => updateField("delay", [Number(e.target.value), (val as number[])?.[1] ?? 5])} min={f.min} max={f.max}
              className="w-14 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
            <span>~</span>
            <input type="number" value={(val as number[])?.[1] ?? 5} onChange={e => updateField("delay", [(val as number[])?.[0] ?? 3, Number(e.target.value)])} min={f.min} max={f.max}
              className="w-14 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
            <span className="text-[11px] text-slate-400">{f.unit}</span>
          </div>
        );
    }
  };

  return (
    <Section icon={Layers} title="平台引擎设置">
      <div className="flex gap-1.5 py-2.5">
        {supported.map(({ id, label }) => (
          <button key={id} onClick={() => setPlatform(id)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${platform === id ? "border-indigo-300 bg-indigo-50 text-indigo-600 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-400" : "border-white/20 bg-white/50 text-slate-500 hover:border-slate-200 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-400"}`}>
            {label}
          </button>
        ))}
        {supported.length === 0 && (
          <span className="py-2 text-xs text-slate-400">当前模式没有支持的平台</span>
        )}
      </div>
      <div>
        <button onClick={() => setEngineOpen(!engineOpen)} className="flex items-center gap-1.5 w-full py-2 text-xs font-medium text-slate-500 hover:text-slate-700 transition-colors dark:text-slate-400 dark:hover:text-slate-300">
          <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${engineOpen ? "" : "-rotate-90"}`} strokeWidth={1.5} />
          {supported.find(p => p.id === platform)?.label} · {MODE_META[mode]?.label ?? mode} 选项
        </button>
        {engineOpen && fields.map(f => <Row key={f.key} label={f.label} desc={f.desc}>{renderField(f)}</Row>)}
        {engineOpen && hasVariants && (
          <ApiVariantsSection engineCfg={engineCfg} mode={mode} variants={apiVariants} saveSite={saveSite} />
        )}
      </div>
    </Section>
  );
}

function ApiVariantsSection({ engineCfg, mode, variants, saveSite }: {
  engineCfg: Record<string, unknown>;
  mode: string;
  variants: string[];
  saveSite: ReturnType<typeof useSaveSiteConfig>;
}) {
  const [variant, setVariant] = useState(variants[0]);
  const pCfg = (engineCfg[variant] as Record<string, unknown> | undefined) ?? {};
  const [showKey, setShowKey] = useState(false);

  const updateVariant = (key: string, value: unknown) => {
    saveSite.mutate({ [mode]: { [variant]: { [key]: value } } });
  };

  return (
    <div className="border-t border-slate-100 dark:border-slate-800/50 pt-2 mt-2">
      <div className="flex gap-1.5 py-2">
        {variants.map(p => (
          <button key={p} onClick={() => setVariant(p)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium uppercase transition-all ${variant === p ? "border-indigo-300 bg-indigo-50 text-indigo-600 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-400" : "border-white/20 bg-white/50 text-slate-500 hover:border-slate-200 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-400"}`}>
            {p}
          </button>
        ))}
      </div>
      <Row label="KEY">
        <div className="flex items-center gap-1">
          <input type="text" placeholder="在此输入 API Key" value={String(pCfg.key ?? "")} onChange={e => updateVariant("key", e.target.value)}
            className={cn("w-40 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400/30 dark:border-slate-600 dark:bg-slate-800/50 dark:text-slate-300 transition-opacity", showKey ? "opacity-100" : "opacity-0 pointer-events-none")} />
          <button onClick={() => setShowKey(!showKey)}
            className="rounded-lg p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors shrink-0">
            {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
        </div>
      </Row>
      <Row label="请求延迟">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <input type="number" value={(pCfg.delay as number[])?.[0] ?? 3} onChange={e => updateVariant("delay", [Number(e.target.value), (pCfg.delay as number[])?.[1] ?? 5])}
            className="w-14 rounded-lg border border-white/20 bg-white/50 px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300" />
          <span>~</span>
          <input type="number" value={(pCfg.delay as number[])?.[1] ?? 5} onChange={e => updateVariant("delay", [(pCfg.delay as number[])?.[0] ?? 3, Number(e.target.value)])}
            className="w-14 rounded-lg border border-white/20 bg-white/50 px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300" />
          <span className="text-[11px] text-slate-400">秒</span>
        </div>
      </Row>
      <Row label="超时"><Num value={Number(pCfg.timeout) || 30} onChange={v => updateVariant("timeout", v)} min={5} max={120} unit="秒" /></Row>
      <Row label="重试次数"><Num value={Number(pCfg.retry_times) || 3} onChange={v => updateVariant("retry_times", v)} min={0} max={10} /></Row>
      <Row label="退避因子" desc="重试间隔倍增系数"><Num value={Number(pCfg.backoff_factor) || 2} onChange={v => updateVariant("backoff_factor", v)} min={1} max={10} /></Row>
    </div>
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
  const { data: sources } = useSources();
  // 模式列表从 sources capabilities 动态生成（同搜索页），已知模式固定顺序
  const modeOptions = useMemo(() => {
    const set = new Set<string>();
    if (sources) {
      for (const info of Object.values(sources)) {
        for (const m of Object.keys(info.capabilities)) set.add(m);
      }
    }
    const ordered: string[] = KNOWN_MODE_ORDER.filter(m => set.has(m));
    for (const m of set) if (!(KNOWN_MODE_ORDER as readonly string[]).includes(m)) ordered.push(m);
    return ordered;
  }, [sources]);
  const availableModes = modeOptions.length > 0 ? modeOptions : [...KNOWN_MODE_ORDER];
  const mode = availableModes.includes(globalConfig.mode) ? globalConfig.mode : availableModes[0];

  const updateGlobal = useCallback((key: string, value: unknown) => {
    saveGlobal.mutateAsync({ ...globalConfig, [key]: value })
      .then(() => toast("设置已保存", "success"))
      .catch(() => toast("设置保存失败", "error"));
    onUpdate(key, value);
  }, [globalConfig, saveGlobal, onUpdate, toast]);

  return (
    <div className="mx-auto max-w-[640px] space-y-4">
      <Section icon={Download} title="下载引擎">
        <Row label="下载模式">
          <div className="flex gap-1.5">
            {availableModes.map(id => {
              const meta = MODE_META[id] ?? { label: id, icon: Zap, desc: "" };
              const Icon = meta.icon;
              return (
                <button key={id} onClick={() => updateGlobal("mode", id)}
                  className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all ${mode === id ? "border-indigo-300 bg-indigo-50 text-indigo-600 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-400" : "border-white/20 bg-white/50 text-slate-500 hover:border-slate-200 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-400"}`}>
                  <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />{meta.label}
                </button>
              );
            })}
          </div>
        </Row>
      </Section>

      <EngineSection mode={mode} />

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
