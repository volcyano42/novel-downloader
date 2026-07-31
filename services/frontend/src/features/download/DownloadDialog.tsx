import { useState, useEffect } from "react";
import { Download, Monitor, Globe, Zap, Loader2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

interface DownloadDialogProps {
  open: boolean; onClose: () => void;
  novelTitle: string; chapterCount: number;
  variant?: "download" | "check";
  initialMode?: string;
  initialProvider?: string;
  availableModes?: string[];
  providers?: string[];
  onStart: (mode: string, provider?: string) => void;
}

const MODE_ICONS: Record<string, typeof Monitor> = { browser: Monitor, requests: Globe, api: Zap };
const MODE_LABELS: Record<string, string> = { browser: "Browser", requests: "Requests", api: "API" };
const MODE_DESCS: Record<string, string> = {
  browser: "模拟浏览器，最稳定",
  requests: "直接 HTTP 请求，最快",
  api: "第三方接口",
};

export function DownloadDialog({ open, onClose, novelTitle, chapterCount, variant = "download", initialMode, initialProvider, availableModes, providers = [], onStart }: DownloadDialogProps) {
  const [mode, setMode] = useState(initialMode ?? "browser");
  const [provider, setProvider] = useState(initialProvider ?? "");
  const [loading, setLoading] = useState(false);
  const [shakeProvider, setShakeProvider] = useState(false);

  const modes = (availableModes && availableModes.length > 0) ? availableModes : ["browser", "requests", "api"];
  const hasApiProviders = providers.length > 0;
  const visibleModes = hasApiProviders ? modes : modes.filter(m => m !== "api");

  useEffect(() => {
    if (open) {
      const defaultMode = initialMode && visibleModes.includes(initialMode) ? initialMode : visibleModes[0] ?? "browser";
      setMode(defaultMode);
      setProvider(initialProvider ?? "");
      setLoading(false);
      setShakeProvider(false);
    }
  }, [open, initialMode, initialProvider, providers.length]);

  const handleStart = () => {
    if (mode === "api" && !provider && providers.length > 0) {
      setShakeProvider(true);
      setTimeout(() => setShakeProvider(false), 400);
      return;
    }
    setLoading(true);
    onStart(mode, mode === "api" && provider ? provider : undefined);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div onClick={e => e.stopPropagation()}
        className="w-[400px] max-h-[80vh] overflow-y-auto rounded-2xl border border-white/20 bg-white/95 backdrop-blur-xl shadow-2xl p-6 animate-in zoom-in-95 fade-in duration-200">
        <h2 className="text-base font-semibold text-slate-800 mb-1">{variant === "check" ? "检查更新设置" : "下载设置"}</h2>
        <p className="text-xs text-slate-500 mb-4 truncate">{variant === "check" ? novelTitle : `${novelTitle} · ${chapterCount} 章`}</p>

        <div className="space-y-2 mb-4">
          {visibleModes.map(id => {
            const Icon = MODE_ICONS[id] ?? Globe;
            return (
              <button key={id} onClick={() => { setMode(id); if (id !== "api") setProvider(""); }}
                className={cn(
                  "w-full flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all",
                  mode === id
                    ? "border-indigo-300 bg-indigo-50 dark:border-indigo-500/40 dark:bg-indigo-500/15"
                    : "border-white/20 bg-white/60 hover:border-slate-200"
                )}>
                <Icon className={cn("h-5 w-5 shrink-0", mode === id ? "text-indigo-500" : "text-slate-400")} strokeWidth={1.5} />
                <div className="min-w-0 flex-1">
                  <span className={cn("text-sm font-medium", mode === id ? "text-indigo-600 dark:text-indigo-400" : "text-slate-700")}>{MODE_LABELS[id] ?? id}</span>
                  <p className="text-[11px] text-slate-400">{MODE_DESCS[id] ?? ""}</p>
                </div>
              </button>
            );
          })}
        </div>

      {mode === "api" && providers.length > 0 && (
        <div className={cn(
          "mb-4 rounded-xl border px-4 py-3 transition-colors",
          shakeProvider
            ? "border-red-300 bg-red-50 animate-shake"
            : "border-indigo-200 bg-indigo-50/50"
        )}>
          <p className="text-[11px] text-slate-400 mb-2">选择接口提供商</p>
          <div className="flex items-center gap-1.5 flex-wrap">
            {providers.map(p => (
              <span key={p} onClick={() => { setProvider(prev => prev === p ? "" : p); }}
                className={cn(
                  "rounded-md px-2.5 py-1 text-[11px] font-medium cursor-pointer transition-colors",
                  provider === p
                    ? "bg-indigo-500 text-white"
                    : "bg-white text-slate-500 hover:bg-slate-100 border border-slate-200"
                )}>{p}</span>
            ))}
          </div>
        </div>
      )}

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
