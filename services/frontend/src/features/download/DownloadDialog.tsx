import { useState, useEffect } from "react";
import { Download, Monitor, Globe, Zap, ChevronDown, Loader2, RefreshCw } from "lucide-react";
import { configApi, type AppConfig } from "@/api/config";
import { cn } from "@/lib/utils";

interface DownloadDialogProps {
  open: boolean; onClose: () => void;
  novelTitle: string; chapterCount: number;
  variant?: "download" | "check";
  initialMode?: string;
  initialProvider?: string;
  onStart: (mode: string, provider?: string) => void;
}

const MODES = [
  { id: "browser", label: "Browser", icon: Monitor, desc: "模拟浏览器，最稳定" },
  { id: "requests", label: "Requests", icon: Globe, desc: "直接 HTTP 请求，最快" },
  { id: "api", label: "API", icon: Zap, desc: "第三方接口" },
] as const;

function ModeField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1 text-[11px]">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-700 font-mono">{value}</span>
    </div>
  );
}

export function DownloadDialog({ open, onClose, novelTitle, chapterCount, variant = "download", initialMode, initialProvider, onStart }: DownloadDialogProps) {
  const [mode, setMode] = useState(initialMode ?? "browser");
  const [provider, setProvider] = useState(initialProvider ?? "");
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [advOpen, setAdvOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (open) configApi.get().then(setCfg).catch(() => {}); }, [open]);
  useEffect(() => { if (open) { setMode(initialMode ?? "browser"); setProvider(initialProvider ?? ""); setLoading(false); } }, [open, initialMode, initialProvider]);

  const modeCfg = cfg?.[mode as keyof typeof cfg] as Record<string, unknown> | undefined;
  const apiMap = cfg?.api_providers ?? {};
  const uniqueProviders = [...new Set(Object.values(apiMap).flat())];

  const handleStart = () => {
    setLoading(true);
    onStart(mode, mode === "api" && provider ? provider : undefined);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div onClick={e => e.stopPropagation()}
        className="w-[400px] max-h-[80vh] overflow-y-auto rounded-2xl border border-white/20 bg-white/95 backdrop-blur-xl shadow-2xl p-6 animate-in zoom-in-95 fade-in duration-200">
        {/* header */}
        <h2 className="text-base font-semibold text-slate-800 mb-1">{variant === "check" ? "检查更新设置" : "下载设置"}</h2>
        <p className="text-xs text-slate-500 mb-4 truncate">{variant === "check" ? novelTitle : `${novelTitle} · ${chapterCount} 章`}</p>

        {/* mode selector */}
        <div className="space-y-2 mb-4">
          {MODES.map(({ id, label, icon: Icon, desc }) => {
            const isApi = id === "api";
            return (
            <button key={id} onClick={() => { setMode(id); if (!isApi) setProvider(""); }}
              className={cn(
                "w-full flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all",
                mode === id
                  ? "border-indigo-300 bg-indigo-50 dark:border-indigo-500/40 dark:bg-indigo-500/15"
                  : "border-white/20 bg-white/60 hover:border-slate-200"
              )}>
              <Icon className={cn("h-5 w-5 shrink-0", mode === id ? "text-indigo-500" : "text-slate-400")} strokeWidth={1.5} />
              <div className="min-w-0 flex-1">
                <span className={cn("text-sm font-medium", mode === id ? "text-indigo-600 dark:text-indigo-400" : "text-slate-700")}>{label}</span>
                <p className="text-[11px] text-slate-400">{desc}</p>
              </div>
              {/* 右侧：API provider 选择 */}
              {isApi && mode === "api" && uniqueProviders.length > 0 && (
                <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
                  {uniqueProviders.map(p => (
                    <span key={p} onClick={() => setProvider(prev => prev === p ? "" : p)}
                      className={cn(
                        "rounded-md px-2 py-0.5 text-[11px] font-medium cursor-pointer transition-colors",
                        provider === p
                          ? "bg-indigo-500 text-white"
                          : "bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                      )}>{p}</span>
                  ))}
                </div>
              )}
            </button>
          )})}
        </div>

        {/* advanced options */}
        {modeCfg && (
          <div className="mb-4">
            <button onClick={() => setAdvOpen(!advOpen)}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 transition-colors">
              <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", advOpen ? "" : "-rotate-90")} strokeWidth={1.5} />
              {MODES.find(m => m.id === mode)?.label} 当前配置
            </button>
            {advOpen && (
              <div className="mt-2 rounded-xl border border-white/20 bg-white/60 backdrop-blur-sm px-3 py-2 space-y-0.5">
                {Object.entries(modeCfg).map(([k, v]) => (
                  <ModeField key={k} label={k} value={Array.isArray(v) ? v.join(" ~ ") : String(v)} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* actions */}
        <div className="flex gap-2">
          <button onClick={onClose}
            className="flex-1 rounded-xl border border-white/20 bg-white/60 backdrop-blur-sm py-2.5 text-sm text-slate-500 hover:bg-slate-50 transition-colors">
            取消
          </button>
          <button onClick={handleStart} disabled={loading}
            className="flex-1 rounded-xl bg-indigo-500 text-white py-2.5 text-sm font-medium hover:bg-indigo-600 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-60">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} /> : variant === "check" ? <RefreshCw className="h-4 w-4" strokeWidth={2} /> : <Download className="h-4 w-4" strokeWidth={2} />}
            {loading ? "启动中..." : variant === "check" ? "开始检查" : `开始下载 (${chapterCount}章)`}
          </button>
        </div>
      </div>
    </div>
  );
}