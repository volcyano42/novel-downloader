import {useEffect, useState} from "react";
import {Globe} from "lucide-react";
import {cn} from "@/lib/utils";
import type {SourceOption} from "@/api/endpoints";

interface SourcePickerDialogProps {
  open: boolean; onClose: () => void;
  novelTitle: string;
  /** 全部书源（来自 useSources()；含 enabled，未启用的源仅标注、仍可选） */
  sources: SourceOption[];
  /** 当前书源（有效来源） */
  current?: string;
  /** 换源请求进行中：禁用并改写确定按钮 */
  submitting?: boolean;
  onPick: (source: string) => void;
}

export function SourcePickerDialog({ open, onClose, novelTitle, sources = [], current, submitting = false, onPick }: SourcePickerDialogProps) {
  const [selected, setSelected] = useState(current ?? sources[0]?.name ?? "");

  // 打开时同步一次：保留仍在列表中的当前选择，否则回退到当前书源 / 第一项。
  useEffect(() => {
    if (!open) return;
    setSelected(prev => {
      if (prev && sources.some(s => s.name === prev)) return prev;
      if (current && sources.some(s => s.name === current)) return current;
      return sources[0]?.name ?? "";
    });
  }, [open, current, sources]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div onClick={e => e.stopPropagation()}
        className="w-[400px] max-h-[80vh] overflow-y-auto rounded-2xl border border-white/20 bg-white/95 backdrop-blur-xl shadow-2xl p-6 animate-in zoom-in-95 fade-in duration-200">
        <h2 className="text-base font-semibold text-slate-800 mb-1">选择书源</h2>
        <p className="text-xs text-slate-500 mb-4 truncate">{novelTitle}</p>

        <div className="space-y-2 mb-4">
          {sources.map(({name, enabled}) => (
            <button key={name} onClick={() => setSelected(name)}
              className={cn(
                "w-full flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all",
                selected === name
                  ? "border-indigo-300 bg-indigo-50 dark:border-indigo-500/40 dark:bg-indigo-500/15"
                  : "border-white/20 bg-white/60 hover:border-slate-200"
              )}>
              <Globe className={cn("h-5 w-5 shrink-0", selected === name ? "text-indigo-500" : "text-slate-400")} strokeWidth={1.5} />
              <span className="flex min-w-0 flex-1 items-center gap-1.5">
                <span className={cn("truncate text-sm font-medium", selected === name ? "text-indigo-600 dark:text-indigo-400" : "text-slate-700")}>{name}</span>
                {!enabled && <span className="shrink-0 text-[10px] text-slate-400">未启用</span>}
              </span>
              {name === current && (
                <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">当前</span>
              )}
            </button>
          ))}
          {sources.length === 0 && <p className="py-2 text-xs text-slate-400">无可用书源，请在设置中启用书源</p>}
        </div>

        <div className="flex gap-2">
          <button onClick={onClose}
            className="flex-1 rounded-xl border border-white/20 bg-white/60 backdrop-blur-sm py-2.5 text-sm text-slate-500 hover:bg-slate-50 transition-colors">
            取消
          </button>
          <button onClick={() => selected && onPick(selected)} disabled={submitting || !selected}
            className="flex-1 rounded-xl bg-indigo-500 text-white py-2.5 text-sm font-medium hover:bg-indigo-600 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-60">
            {submitting ? "保存中…" : "确定"}
          </button>
        </div>
      </div>
    </div>
  );
}
