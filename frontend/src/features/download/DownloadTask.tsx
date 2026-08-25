import {useState} from "react";
import {AlertTriangle, CheckCircle, ChevronDown, Loader2, Pause, Play, RefreshCw, X, XCircle} from "lucide-react";
import {cn} from "@/lib/utils";
import {Tooltip, TooltipContent, TooltipProvider, TooltipTrigger} from "@/components/ui/tooltip";
import type {ChapterStatus} from "@/api/endpoints";

type TaskStatus = "downloading" | "paused" | "completed" | "failed" | "partial" | "cancelled";

interface DownloadTaskProps {
  title: string; status: TaskStatus; progress?: number; errorMessage?: string; currentTitle?: string;
  chapters?: ChapterStatus[];
  onPause?: () => void; onResume?: () => void; onCancel?: () => void; onRetry?: () => void; className?: string;
}

const statusConfig: Record<TaskStatus, { label: string; className: string; icon: typeof CheckCircle }> = {
  downloading: { label: "下载中",  className: "bg-[#5e6ad2]/10 text-[#5e6ad2]", icon: Loader2 },
  paused:     { label: "已暂停", className: "bg-amber-50 text-amber-600", icon: Pause },
  completed:  { label: "完成",   className: "bg-emerald-50 text-emerald-600", icon: CheckCircle },
  failed:     { label: "失败",   className: "bg-red-50 text-red-500", icon: XCircle },
  partial:    { label: "部分完成",className: "bg-amber-50 text-amber-600", icon: AlertTriangle },
  cancelled:  { label: "已取消", className: "bg-slate-100 text-slate-500", icon: X },
};

function ChapterRow({ ch }: { ch: ChapterStatus }) {
  return (
    <div className="flex items-center gap-2 py-1.5 text-xs">
      <span className="shrink-0 w-4 flex justify-center">
        {ch.status === "downloading" && <Loader2 className="h-3 w-3 text-[#5e6ad2] animate-spin" strokeWidth={2.5} />}
        {ch.status === "pending" && <span className="block h-1.5 w-1.5 rounded-full bg-slate-300" />}
        {ch.status === "downloaded" && <CheckCircle className="h-3 w-3 text-emerald-500" strokeWidth={2.5} />}
        {ch.status === "failed" && <XCircle className="h-3 w-3 text-red-400" strokeWidth={2.5} />}
      </span>
      <span className={cn(
        "truncate flex-1",
        ch.status === "downloading" && "text-[#5e6ad2] font-medium",
        ch.status === "downloaded" && "text-slate-400",
        ch.status === "failed" && "text-red-400 line-through",
      )}>{ch.title}</span>
      <span className={cn(
        "shrink-0 text-[10px]",
        ch.status === "downloading" && "text-[#5e6ad2]",
        ch.status === "pending" && "text-slate-300",
        ch.status === "downloaded" && "text-emerald-500",
        ch.status === "failed" && "text-red-400",
      )}>
        {ch.status === "downloading" && "下载中"}
        {ch.status === "pending" && "待下载"}
        {ch.status === "downloaded" && "✓已下载"}
        {ch.status === "failed" && "失败"}
      </span>
    </div>
  );
}

function ChapterRowSkeleton() {
  return (
    <div className="flex items-center gap-2 py-1.5">
      <span className="h-3 w-3 shrink-0 animate-pulse rounded-full bg-slate-200" />
      <span className="h-3 w-3/4 animate-pulse rounded bg-slate-200" />
    </div>
  );
}

export function DownloadTaskSkeleton() {
  // 任务卡片骨架（仿 BookCardSkeleton 的 animate-pulse 风格）
  return (
    <div className="rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl shadow-card px-4 py-3">
      <div className="h-4 w-2/3 animate-pulse rounded bg-slate-200" />
      <div className="mt-2 flex items-center gap-2">
        <div className="h-1.5 w-[120px] animate-pulse rounded-lg bg-slate-200" />
        <div className="h-3 w-8 animate-pulse rounded bg-slate-200" />
      </div>
    </div>
  );
}

export function DownloadTask({ title, status, progress = 0, errorMessage, currentTitle, chapters = [], onPause, onResume, onCancel, onRetry, className }: DownloadTaskProps) {
  const cfg = statusConfig[status]; const Icon = cfg.icon;
  const showProgress = status === "downloading" || status === "paused";
  const [expanded, setExpanded] = useState(false);

  // 章节可见范围：completed/partial 展开全部（显示成功/失败章节）；
  // 下载中/暂停取「第一个非 downloaded 章节起的前 10 个」避免面板过长
  const visible = status === "completed" || status === "partial"
    ? chapters
    : (() => {
        const firstActive = chapters.findIndex(c => c.status !== "downloaded");
        return firstActive >= 0
          ? chapters.slice(firstActive, firstActive + 10)
          : chapters.slice(0, 10);
      })();
  const hasPanel = chapters.length > 0 || showProgress;

  return (
    <div className={cn(
      "rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl shadow-card transition-all duration-300",
      (status === "completed" || status === "partial") && "animate-[complete-flash_0.5s_ease-out]",
      status === "cancelled" && "opacity-60",
      className,
    )}>
      {/* 头部 */}
      <button
        onClick={() => hasPanel && setExpanded(!expanded)}
        className="flex items-center gap-3 w-full px-4 py-3 text-left"
      >
        <div className="min-w-0 flex-1">
          <span className="truncate block text-sm font-medium text-slate-800">{title}</span>
          {currentTitle && status === "downloading" && (
            <span className="truncate block text-[11px] text-slate-400 mt-0.5">{currentTitle}</span>
          )}
          {showProgress && (
            <div className="mt-1.5 flex items-center gap-2">
              <div className="flex-1 max-w-[120px]"><div className="relative h-1.5 overflow-hidden rounded-lg bg-slate-200">
                <div className="h-full rounded-lg bg-[#5e6ad2] transition-all duration-300" style={{ width: `${progress}%` }} />
                {status === "downloading" && <div className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-white/40 to-transparent" />}
              </div></div>
              <span className="text-[11px] text-slate-400 tabular-nums">{progress}%</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={cn("inline-flex items-center gap-1 rounded-lg px-2.5 py-0.5 text-xs font-medium", cfg.className)}>
            <Icon className={cn("h-3 w-3", status === "downloading" && "animate-spin")} strokeWidth={2} />{cfg.label}
          </span>
          {status === "downloading" && onPause &&
            <button onClick={e => { e.stopPropagation(); onPause(); }} className="rounded-lg p-1 text-slate-400 hover:text-amber-500 transition-colors"><Pause className="h-4 w-4" strokeWidth={1.5} /></button>}
          {status === "paused" && onResume &&
            <button onClick={e => { e.stopPropagation(); onResume(); }} className="rounded-lg p-1 text-slate-400 hover:text-[#5e6ad2] transition-colors"><Play className="h-4 w-4" strokeWidth={1.5} /></button>}
          {(status === "downloading" || status === "paused") && onCancel &&
            <button onClick={e => { e.stopPropagation(); onCancel(); }} className="rounded-lg p-1 text-slate-400 hover:text-red-500 transition-colors"><X className="h-4 w-4" strokeWidth={1.5} /></button>}
          {status === "failed" && onRetry && (
            <TooltipProvider><Tooltip><TooltipTrigger asChild>
              <button onClick={e => { e.stopPropagation(); onRetry(); }} className="rounded-lg p-1 text-red-400 hover:text-red-600 transition-colors"><RefreshCw className="h-4 w-4" strokeWidth={1.5} /></button>
            </TooltipTrigger>{errorMessage && <TooltipContent side="left"><p className="max-w-[200px]">{errorMessage}</p></TooltipContent>}</Tooltip></TooltipProvider>
          )}
          {hasPanel && (
            <ChevronDown className={cn("h-3.5 w-3.5 text-slate-300 transition-transform duration-300", expanded && "rotate-180")} strokeWidth={1.5} />
          )}
        </div>
      </button>

      {/* 折叠面板：章节队列 */}
      <div className={cn(
        "grid transition-all duration-300 ease-out",
        expanded && hasPanel ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
      )}>
        <div className="overflow-hidden">
          <div className="min-w-0 px-4 pb-3 border-t border-slate-100">
            <div className="pt-2 space-y-0.5">
              {visible.length === 0
                ? Array.from({ length: 3 }).map((_, i) => <ChapterRowSkeleton key={i} />)
                : visible.map((ch, i) => (
                    <ChapterRow key={`${ch.order}-${ch.title}-${i}`} ch={ch} />
                  ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
