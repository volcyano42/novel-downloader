import { useState } from "react";
import { Download, Settings, Check, Loader2, ChevronDown, Gauge, Package, Monitor, Globe, Zap, Bell, Layers } from "lucide-react";
import type { AppConfig } from "@/api/config";

// ── tiny helpers ──

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

function Range({ value, onChange, min, max, left, right }: { value: number; onChange: (v: number) => void; min: number; max: number; left: string; right: string }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div className="flex flex-col gap-0.5 w-full max-w-[200px] group">
      <div className="relative h-4">
        <span className="absolute text-[11px] font-semibold text-indigo-500 tabular-nums -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity" style={{ left: `${pct}%` }}>{value}</span>
      </div>
      <input type="range" min={min} max={max} value={value} onChange={e => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full bg-slate-200 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-indigo-500 [&::-webkit-slider-thumb]:cursor-pointer dark:bg-slate-700" />
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

// ── main ──

interface SettingsViewProps {
  cfg: AppConfig;
  saving: boolean;
  saved: boolean;
  onUpdate: (path: string, value: unknown) => void;
  onSave: () => void;
}

const PLATFORMS = [
  { id: "fanqie", label: "番茄" },
  { id: "qidian", label: "起点" },
  { id: "qimao", label: "七猫" },
] as const;

const ENGINES = [
  { id: "browser", label: "Browser", icon: Monitor, desc: "模拟浏览器，最稳定" },
  { id: "requests", label: "Requests", icon: Globe, desc: "直接 HTTP，最快" },
  { id: "api", label: "API", icon: Zap, desc: "第三方接口" },
] as const;

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
  api: [
    { key: "delay", label: "请求延迟", desc: "两章之间随机等待", type: "range-delay", min: 0, max: 30, unit: "秒" },
    { key: "timeout", label: "超时", desc: "单次请求最长等待", type: "num", min: 5, max: 120, unit: "秒" },
    { key: "retry_times", label: "重试次数", type: "num", min: 0, max: 10 },
    { key: "backoff_factor", label: "退避因子", desc: "重试间隔倍增系数", type: "num", min: 1, max: 10 },
  ],
};

export function SettingsView({ cfg, saving, saved, onUpdate, onSave }: SettingsViewProps) {
  const [engineOpen, setEngineOpen] = useState(false);
  const [platform, setPlatform] = useState<string>(PLATFORMS[0].id);

  // 平台引擎配置：优先 platforms.{platform}.{mode}，回退顶层 {mode}
  const platforms = cfg.platforms ?? {};
  const getEngineCfg = () => {
    const platCfg = platforms[platform];
    if (platCfg) return platCfg[cfg.mode as "browser" | "requests" | "api"] as unknown as Record<string, unknown>;
    // 回退：旧版全局引擎配置
    return cfg[cfg.mode as "browser" | "requests" | "api"] as unknown as Record<string, unknown>;
  };
  const engineCfg = getEngineCfg();
  const fields = ENGINE_FIELDS[cfg.mode] ?? [];

  // 引擎字段更新路径前缀
  const engPath = platforms[platform] ? `platforms.${platform}.${cfg.mode}` : cfg.mode;

  const renderField = (f: typeof fields[number]) => {
    const val = engineCfg[f.key];
    switch (f.type) {
      case "toggle":
        return <Toggle checked={!!val} onChange={v => onUpdate(`${engPath}.${f.key}`, v)} />;
      case "select":
        return <Select value={String(val ?? f.opts![0].value)} onChange={v => onUpdate(`${engPath}.${f.key}`, v)} options={f.opts!} />;
      case "num":
        return <Num value={Number(val) || 0} onChange={v => onUpdate(`${engPath}.${f.key}`, v)} min={f.min} max={f.max} unit={f.unit} />;
      case "text":
        return <input type="text" value={String(val ?? "")} onChange={e => onUpdate(`${engPath}.${f.key}`, e.target.value)}
          className="w-40 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2.5 py-1.5 text-xs text-slate-700 outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />;
      case "range-delay":
        return (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <input type="number" value={(val as number[])?.[0] ?? 3} onChange={e => onUpdate(`${engPath}.delay`, [Number(e.target.value), (val as number[])?.[1] ?? 5])} min={f.min} max={f.max}
              className="w-14 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
            <span>~</span>
            <input type="number" value={(val as number[])?.[1] ?? 5} onChange={e => onUpdate(`${engPath}.delay`, [(val as number[])?.[0] ?? 3, Number(e.target.value)])} min={f.min} max={f.max}
              className="w-14 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
            <span className="text-[11px] text-slate-400">{f.unit}</span>
          </div>
        );
    }
  };

  return (
    <div className="mx-auto max-w-[640px] space-y-4">
      {/* ── 下载引擎 ── */}
      <Section icon={Download} title="下载引擎">
        <Row label="下载模式">
          <div className="flex gap-1.5">
            {ENGINES.map(({ id, label, icon: Icon }) => (
              <button key={id} onClick={() => onUpdate("mode", id)}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all ${cfg.mode === id ? "border-indigo-300 bg-indigo-50 text-indigo-600 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-400" : "border-white/20 bg-white/50 text-slate-500 hover:border-slate-200 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-400"}`}>
                <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />{label}
              </button>
            ))}
          </div>
        </Row>
      </Section>

      {/* ── 平台引擎设置 ── */}
      <Section icon={Layers} title="平台引擎设置">
        {/* 平台选择 tab */}
        <div className="flex gap-1.5 py-2.5">
          {PLATFORMS.map(({ id, label }) => (
            <button key={id} onClick={() => setPlatform(id)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${platform === id ? "border-indigo-300 bg-indigo-50 text-indigo-600 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-400" : "border-white/20 bg-white/50 text-slate-500 hover:border-slate-200 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-400"}`}>
              {label}
            </button>
          ))}
        </div>
        <div>
          <button onClick={() => setEngineOpen(!engineOpen)} className="flex items-center gap-1.5 w-full py-2 text-xs font-medium text-slate-500 hover:text-slate-700 transition-colors dark:text-slate-400 dark:hover:text-slate-300">
            <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${engineOpen ? "" : "-rotate-90"}`} strokeWidth={1.5} />
            {PLATFORMS.find(p => p.id === platform)?.label} · {ENGINES.find(e => e.id === cfg.mode)?.label} 选项
          </button>
          {engineOpen && fields.map(f => <Row key={f.key} label={f.label} desc={f.desc}>{renderField(f)}</Row>)}
        </div>
      </Section>

      {/* ── 并发 ── */}
      <Section icon={Gauge} title="并发与性能">
        <Row label="并发线程数" desc="同时下载的章节数">
          <Range value={cfg.max_workers} onChange={v => onUpdate("max_workers", v)} min={1} max={10} left="1" right="10" />
        </Row>
        <Row label="提示" desc="💡 建议 3-5，Browser 模式建议 1-3，过高触发反爬拦截"><span /></Row>
      </Section>

      {/* ── 导出格式 ── */}
      <Section icon={Package} title="导出格式">
        <Row label="格式">
          <div className="flex gap-1.5">
            {(["txt", "epub", "img"] as const).map(fmt => (
              <button key={fmt} onClick={() => onUpdate(`${fmt}.enabled`, !cfg[fmt].enabled)}
                className={`flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-semibold uppercase transition-all ${cfg[fmt].enabled ? "border-indigo-300 bg-indigo-50 text-indigo-600 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-400" : "border-white/20 bg-white/50 text-slate-400 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-500"}`}>
                {cfg[fmt].enabled && <Check className="h-3 w-3" strokeWidth={2.5} />}{fmt}
              </button>
            ))}
          </div>
        </Row>
      </Section>

      {cfg.txt.enabled && (
        <Section icon={Package} title="TXT 纯文本">
          <Row label="编码"><Select value={cfg.txt.encoding} onChange={v => onUpdate("txt.encoding", v)} options={[{ value: "utf-8", label: "UTF-8" }, { value: "gbk", label: "GBK" }]} /></Row>
        </Section>
      )}
      {cfg.epub.enabled && (
        <Section icon={Package} title="EPUB 电子书">
          <Row label="压缩算法"><Select value={cfg.epub.compression} onChange={v => onUpdate("epub.compression", v)} options={[{ value: "deflate", label: "Deflate" }, { value: "bzip2", label: "BZip2" }, { value: "stored", label: "Stored" }]} /></Row>
          <Row label="压缩级别"><Num value={cfg.epub.compresslevel} onChange={v => onUpdate("epub.compresslevel", v)} min={1} max={9} /></Row>
          <Row label="优化图片"><Toggle checked={cfg.epub.optimize_images} onChange={v => onUpdate("epub.optimize_images", v)} /></Row>
          <Row label="JPEG 质量"><Num value={cfg.epub.jpeg_quality} onChange={v => onUpdate("epub.jpeg_quality", v)} min={1} max={100} /></Row>
          <Row label="最大图宽"><Num value={cfg.epub.max_image_width} onChange={v => onUpdate("epub.max_image_width", v)} min={0} max={4096} unit="px" /></Row>
          <Row label="包含目录"><Toggle checked={cfg.epub.include_toc} onChange={v => onUpdate("epub.include_toc", v)} /></Row>
        </Section>
      )}
      {cfg.img.enabled && (
        <Section icon={Package} title="IMG 图片序列">
          <Row label="输出格式"><Select value={cfg.img.output_format} onChange={v => onUpdate("img.output_format", v)} options={[{ value: "original", label: "原始" }, { value: "jpeg", label: "JPEG" }, { value: "png", label: "PNG" }, { value: "webp", label: "WebP" }]} /></Row>
        </Section>
      )}

      {/* ── 通知 ── */}
      <Section icon={Bell} title="通知">
        <Row label="下载完成时" desc="全部章节下载成功时触发">
          <Toggle checked={cfg.notify?.on_complete ?? true} onChange={v => onUpdate("notify.on_complete", v)} />
        </Row>
        <Row label="有不完整章节时" desc="部分章节失败或缺失时触发">
          <Toggle checked={cfg.notify?.on_incomplete ?? true} onChange={v => onUpdate("notify.on_incomplete", v)} />
        </Row>
        <Row label="提示音" desc="bell=终端响铃, system=系统通知, none=静默">
          <Select value={cfg.notify?.sound ?? "bell"} onChange={v => onUpdate("notify.sound", v)}
            options={[{ value: "bell", label: "🔔 响铃" }, { value: "system", label: "💻 系统通知" }, { value: "none", label: "🔇 静默" }]} />
        </Row>
      </Section>

      {/* ── Save ── */}
      <div className="sticky bottom-0 z-30 mt-2 py-4 bg-gradient-to-t from-white via-white/95 to-transparent dark:from-slate-950 dark:via-slate-950/95" style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom, 0px))" }}>
        <button onClick={onSave} disabled={saving}
          className={`w-full rounded-2xl py-2.5 text-sm font-semibold transition-all duration-200 flex items-center justify-center gap-2 ${saved ? "bg-emerald-500 text-white" : "bg-indigo-500 text-white hover:bg-indigo-600 active:scale-[0.98] shadow-lg shadow-indigo-500/25"} disabled:opacity-60 disabled:cursor-not-allowed`}>
          {saving ? <><Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />保存中...</> : saved ? <><Check className="h-4 w-4" strokeWidth={2.5} />已保存</> : "💾 保存设置"}
        </button>
      </div>
    </div>
  );
}
