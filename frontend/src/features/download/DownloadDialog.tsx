import {useEffect, useState} from "react";
import {Download, Globe, Loader2, RefreshCw} from "lucide-react";
import {cn} from "@/lib/utils";

interface DownloadDialogProps {
  open: boolean; onClose: () => void;
  novelTitle: string; chapterCount: number;
  dialogMode?: "download" | "check";
  /** 可选书源名列表（来自 `/download/sources`） */
  sources?: string[];
  /** 默认选中的书源 */
  initialSource?: string;
  onStart: (source: string) => void;
}

export function DownloadDialog({ open, onClose, novelTitle, chapterCount, dialogMode = "download", sources = [], initialSource, onStart }: DownloadDialogProps) {
  const [source, setSource] = useState(initialSource ?? sources[0] ?? "");
  const [loading, setLoading] = useState(false);

  // 打开时同步一次：保留仍在列表中的当前选择，否则回退到 initialSource / 第一项。
  useEffect(() => {
    if (!open) return;
    setSource(prev => {
      if (prev && sources.includes(prev)) return prev;
      if (initialSource && sources.includes(initialSource)) return initialSource;
      return sources[0] ?? "";
    });
    setLoading(false);
  }, [open, initialSource, sources]);

  const handleStart = () => {
    if (!source) return;
    setLoading(true);
    onStart(source);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div onClick={e => e.stopPropagation()}
        className="w-[400px] max-h-[80vh] overflow-y-auto rounded-2xl border border-white/20 bg-white/95 backdrop-blur-xl shadow-2xl p-6 animate-in zoom-in-95 fade-in duration-200">
        <h2 className="text-base font-semibold text-slate-800 mb-1">{dialogMode === "check" ? "检查更新设置" : "下载设置"}</h2>
        <p className="text-xs text-slate-500 mb-4 truncate">{dialogMode === "check" ? novelTitle : `${novelTitle} · ${chapterCount} 章`}</p>

        <p className="text-[11px] text-slate-400 mb-2">选择书源</p>
        <div className="space-y-2 mb-4">
          {sources.map(name => (
            <button key={name} onClick={() => setSource(name)}
              className={cn(
                "w-full flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all",
                source === name
                  ? "border-indigo-300 bg-indigo-50 dark:border-indigo-500/40 dark:bg-indigo-500/15"
                  : "border-white/20 bg-white/60 hover:border-slate-200"
              )}>
              <Globe className={cn("h-5 w-5 shrink-0", source === name ? "text-indigo-500" : "text-slate-400")} strokeWidth={1.5} />
              <span className={cn("text-sm font-medium truncate", source === name ? "text-indigo-600 dark:text-indigo-400" : "text-slate-700")}>{name}</span>
            </button>
          ))}
          {sources.length === 0 && <p className="py-2 text-xs text-slate-400">无可用书源，请在设置中启用书源</p>}
        </div>

        <div className="flex gap-2">
          <button onClick={onClose}
            className="flex-1 rounded-xl border border-white/20 bg-white/60 backdrop-blur-sm py-2.5 text-sm text-slate-500 hover:bg-slate-50 transition-colors">
            取消
          </button>
          <button onClick={handleStart} disabled={loading || !source}
            className="flex-1 rounded-xl bg-indigo-500 text-white py-2.5 text-sm font-medium hover:bg-indigo-600 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-60">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} /> : dialogMode === "check" ? <RefreshCw className="h-4 w-4" strokeWidth={2} /> : <Download className="h-4 w-4" strokeWidth={2} />}
            {loading ? "启动中..." : dialogMode === "check" ? "开始检查" : `开始下载 (${chapterCount}章)`}
          </button>
        </div>
      </div>
    </div>
  );
}
