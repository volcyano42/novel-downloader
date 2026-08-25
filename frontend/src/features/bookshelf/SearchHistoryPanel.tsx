import {Trash2} from "lucide-react";
import {useState} from "react";
import {cn} from "@/lib/utils";
import {useDeleteSearchHistory, useSearchHistory} from "@/hooks/index";

interface SearchHistoryPanelProps {
  /** 点击历史条目（非删除模式）：回填搜索框，不自动搜索 */
  onPick: (item: { platform: string; keyword: string; mode?: string; variant?: string }) => void;
}

export function SearchHistoryPanel({ onPick }: SearchHistoryPanelProps) {
  const { data: groups = [] } = useSearchHistory();
  const deleteMut = useDeleteSearchHistory();
  const [deleteMode, setDeleteMode] = useState(false);

  if (groups.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-200/70 bg-white/60 backdrop-blur-sm px-4 py-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-600">搜索历史</span>
        <button
          onClick={() => setDeleteMode(m => !m)}
          className={cn(
            "rounded-lg p-1.5 transition-colors",
            deleteMode ? "bg-red-50 text-red-500" : "text-slate-400 hover:text-slate-600",
          )}
          aria-label={deleteMode ? "退出删除模式" : "删除搜索历史"}
        >
          <Trash2 className="h-4 w-4" strokeWidth={1.5} />
        </button>
      </div>
      <div className="space-y-3">
        {groups.map(g => (
          <div key={g.date_label}>
            {/* 日期：浅色文字 + 上下浅边框（边框略深于文字） */}
            <div className="mb-1 border-y border-slate-200/60 py-0.5">
              <span className="text-[11px] text-slate-300">{g.date_label}</span>
            </div>
            <div className="space-y-0.5">
              {g.items.map(item => (
                <button
                  key={item.id}
                  onClick={() => (deleteMode ? deleteMut.mutate(item.id) : onPick({ platform: item.platform, keyword: item.keyword, mode: item.mode, variant: item.variant }))}
                  className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm text-slate-600 hover:bg-slate-100 transition-colors"
                >
                  <span className="truncate flex-1">{item.keyword}</span>
                  {item.platform && <span className="shrink-0 text-[10px] text-slate-300">{item.platform}</span>}
                  {item.mode && <span className="shrink-0 text-[10px] text-slate-300">{item.mode}</span>}
                  {item.variant && <span className="shrink-0 text-[10px] text-slate-300">{item.variant}</span>}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
