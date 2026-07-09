import { useState } from "react";
import { FileDown, Monitor, Globe, Zap, Loader2, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface ExportDialogProps {
  open: boolean; onClose: () => void;
  novelTitle: string; chapterCount: number;
  onExport: (formats: string[], mode: string, provider?: string) => void;
  defaultMode?: string; defaultProvider?: string;
}

const MODES = [
  { id: "browser", label: "Browser", icon: Monitor, desc: "模拟浏览器，最稳定" },
  { id: "requests", label: "Requests", icon: Globe, desc: "直接 HTTP 请求，最快" },
  { id: "api", label: "API", icon: Zap, desc: "第三方接口" },
] as const;

const FORMATS = [
  { id: "txt", label: "TXT", desc: "纯文本" },
  { id: "epub", label: "EPUB", desc: "电子书" },
  { id: "img", label: "IMG", desc: "图片序列" },
] as const;

export function ExportDialog({ open, onClose, novelTitle, chapterCount, onExport, defaultMode, defaultProvider }: ExportDialogProps) {
  const [selected, setSelected] = useState("txt");
  const [mode, setMode] = useState(defaultMode ?? "requests");
  const [provider, setProvider] = useState(defaultProvider ?? "");
  const [loading, setLoading] = useState(false);

  const handleExport = () => {
    setLoading(true);
    onExport([selected], mode, mode === "api" && provider ? provider : undefined);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div onClick={e => e.stopPropagation()}
        className="w-[400px] max-h-[80vh] overflow-y-auto rounded-2xl border border-white/20 bg-white/95 backdrop-blur-xl shadow-2xl p-6 animate-in zoom-in-95 fade-in duration-200">
        {/* header */}
        <h2 className="text-base font-semibold text-slate-800 mb-1">导出设置</h2>
        <p className="text-xs text-slate-500 mb-4 truncate">{novelTitle} · {chapterCount} 章</p>

        {/* format selector */}
        <p className="text-xs font-medium text-slate-500 mb-2">选择格式</p>
        <div className="space-y-2 mb-5">
          {FORMATS.map(({ id, label, desc }) => {
            const checked = selected === id;
            return (
              <button key={id} onClick={() => setSelected(id)}
                className={cn(
                  "w-full flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all",
                  checked
                    ? "border-indigo-300 bg-indigo-50 dark:border-indigo-500/40 dark:bg-indigo-500/15"
                    : "border-white/20 bg-white/60 hover:border-slate-200"
                )}>
                <div className={cn(
                  "h-5 w-5 shrink-0 rounded-md border-2 flex items-center justify-center transition-colors",
                  checked ? "border-indigo-500 bg-indigo-500" : "border-slate-300"
                )}>
                  {checked && <Check className="h-3 w-3 text-white" strokeWidth={3} />}
                </div>
                <div className="min-w-0 flex-1">
                  <span className={cn("text-sm font-medium", checked ? "text-indigo-600 dark:text-indigo-400" : "text-slate-700")}>{label}</span>
                  <p className="text-[11px] text-slate-400">{desc}</p>
                </div>
              </button>
            );
          })}
        </div>

        {/* mode selector */}
        <p className="text-xs font-medium text-slate-500 mb-2">导出引擎模式</p>
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
            </button>
          )})}
        </div>

        {/* actions */}
        <div className="flex gap-2">
          <button onClick={onClose}
            className="flex-1 rounded-xl border border-white/20 bg-white/60 backdrop-blur-sm py-2.5 text-sm text-slate-500 hover:bg-slate-50 transition-colors">
            取消
          </button>
          <button onClick={handleExport} disabled={loading}
            className="flex-1 rounded-xl bg-indigo-500 text-white py-2.5 text-sm font-medium hover:bg-indigo-600 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-60">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} /> : <FileDown className="h-4 w-4" strokeWidth={2} />}
            {loading ? "导出中..." : "开始导出"}
          </button>
        </div>
      </div>
    </div>
  );
}
