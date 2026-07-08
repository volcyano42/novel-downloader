import { useState, useEffect, useCallback } from "react";
import { BookOpen, Download, FileDown, MoreHorizontal, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { storageApi } from "@/api/storage";
import { exportApi } from "@/api/export";
import { configApi } from "@/api/config";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

interface BookCardProps {
  title: string; author: string; novelId?: string; cover?: string; progress?: number;
  onRead?: () => void; className?: string;
}

export function BookCard({ title, author, novelId, cover, progress = 0, onRead, className }: BookCardProps) {
  const [loadedCover, setLoadedCover] = useState<string | null>(null);
  const [coverLoading, setCoverLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (cover) { setLoadedCover(cover); return; }
    if (!novelId) return;
    let cancelled = false;
    setCoverLoading(true);
    storageApi.getCover(novelId).then(url => {
      if (!cancelled) { setLoadedCover(url); setCoverLoading(false); }
    }).catch(() => { if (!cancelled) setCoverLoading(false); });
    return () => { cancelled = true; };
  }, [novelId, cover]);

  const handleExport = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!novelId || exporting) return;
    setExporting(true);
    try {
      const cfg = await configApi.get();
      const body: Record<string, unknown> = { novel_id: novelId, chapter_id: null };
      if (cfg.txt?.enabled)   body.txt   = cfg.txt;
      if (cfg.epub?.enabled)  body.epub  = cfg.epub;
      if (cfg.img?.enabled)   body.img   = cfg.img;
      const { task_id } = await exportApi.trigger(body);
      // 轮询直到完成
      for (let i = 0; i < 120; i++) {
        await new Promise(r => setTimeout(r, 1000));
        const task = await exportApi.taskStatus(task_id);
        if (task.status === "completed") {
          // 触发浏览器下载
          const a = document.createElement("a");
          a.href = `/api/v1/export/download/${task_id}`;
          a.download = "";
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          break;
        }
        if (task.status === "failed") break;
      }
    } catch { /* ignore */ }
    finally { setExporting(false); }
  }, [novelId, exporting]);

  return (
    <div className={cn("group/card cursor-pointer flex flex-col rounded-2xl border border-white/20 bg-white/80 backdrop-blur-xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-[0_20px_40px_rgb(0,0,0,0.06)] hover:-translate-y-0.5 transition-all duration-300 ease-out", className)}
      onClick={onRead}>
      <div className="aspect-[4/5] overflow-hidden rounded-t-2xl bg-slate-100 p-[25%] relative">
        {loadedCover ? (
          <img src={loadedCover} alt={title} className="h-full w-full object-contain animate-in fade-in duration-300" loading="lazy" />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            {coverLoading
              ? <div className="h-8 w-8 animate-pulse rounded-full bg-slate-300/60" />
              : <BookOpen className="h-10 w-10 text-slate-300" strokeWidth={1.5} />}
          </div>
        )}
        {/* 右下角操作图标 — hover 时显示 */}
        <div className="absolute bottom-1.5 right-1.5 flex items-center gap-0.5 opacity-0 group-hover/card:opacity-100 transition-opacity duration-200">
          <button onClick={e => e.stopPropagation()}
            className="rounded-lg bg-white/80 p-1.5 text-slate-400 hover:text-indigo-500 hover:bg-white transition-colors shadow-sm">
            <Download className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
          <button onClick={handleExport}
            className="rounded-lg bg-white/80 p-1.5 text-slate-400 hover:text-indigo-500 hover:bg-white transition-colors shadow-sm">
            {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} /> : <FileDown className="h-3.5 w-3.5" strokeWidth={2} />}
          </button>
          <button onClick={e => e.stopPropagation()}
            className="rounded-lg bg-white/80 p-1.5 text-slate-400 hover:text-indigo-500 hover:bg-white transition-colors shadow-sm">
            <MoreHorizontal className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-1 px-4 py-3">
        {novelId && <p className="truncate text-[11px] text-slate-400 font-mono">{novelId}</p>}
        <TooltipProvider delayDuration={500}>
          <Tooltip>
            <TooltipTrigger asChild>
              <h3 className="truncate text-base font-semibold text-slate-800">{title}</h3>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[280px] text-xs font-semibold">
              {title}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <p className="text-sm text-slate-500">{author}</p>
        {progress > 0 && <div className="mt-auto pt-2"><div className="h-1.5 rounded-full bg-slate-200"><div className="h-full rounded-full bg-indigo-500 transition-all duration-500" style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} /></div></div>}
      </div>
    </div>
  );
}

export function BookCardSkeleton() {
  return (
    <div className="flex flex-col rounded-2xl border border-white/20 bg-white/80">
      <div className="aspect-[4/5] animate-pulse rounded-t-2xl bg-slate-300/60" />
      <div className="flex flex-col gap-2 px-4 py-3">
        <div className="h-4 w-3/4 animate-pulse rounded bg-slate-300/60" />
        <div className="h-3 w-1/2 animate-pulse rounded bg-slate-300/60" />
      </div>
    </div>
  );
}
