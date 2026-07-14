import { CheckCircle, Loader2, X, XCircle, RefreshCw, Pause, Play } from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

type TaskStatus = "downloading" | "paused" | "completed" | "failed";

interface DownloadTaskProps {
  title: string; status: TaskStatus; progress?: number; errorMessage?: string; currentTitle?: string;
  onPause?: () => void; onResume?: () => void; onCancel?: () => void; onRetry?: () => void; className?: string;
}

const statusConfig: Record<TaskStatus, { label: string; className: string; icon: typeof CheckCircle }> = {
  downloading: { label: "下载中", className: "bg-[#5e6ad2]/10 text-[#5e6ad2]", icon: Loader2 },
  paused:     { label: "已暂停", className: "bg-amber-50 text-amber-600", icon: Pause },
  completed:  { label: "完成",   className: "bg-emerald-50 text-emerald-600", icon: CheckCircle },
  failed:     { label: "失败",   className: "bg-red-50 text-red-500", icon: XCircle },
};

export function DownloadTask({ title, status, progress = 0, errorMessage, currentTitle, onPause, onResume, onCancel, onRetry, className }: DownloadTaskProps) {
  const cfg = statusConfig[status]; const Icon = cfg.icon;
  const showProgress = status === "downloading" || status === "paused";
  return (
    <div className={cn("flex items-center gap-3 rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl px-4 py-3 shadow-card", status === "completed" && "animate-[complete-flash_0.5s_ease-out]", className)}>
      <div className="min-w-0 flex-1">
        <span className="truncate block text-sm font-medium text-slate-800">{title}</span>
        {currentTitle && (
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
          <button onClick={onPause} className="rounded-lg p-1 text-slate-400 hover:text-amber-500 transition-colors"><Pause className="h-4 w-4" strokeWidth={1.5} /></button>}
        {status === "paused" && onResume &&
          <button onClick={onResume} className="rounded-lg p-1 text-slate-400 hover:text-[#5e6ad2] transition-colors"><Play className="h-4 w-4" strokeWidth={1.5} /></button>}
        {(status === "downloading" || status === "paused") && onCancel &&
          <button onClick={onCancel} className="rounded-lg p-1 text-slate-400 hover:text-red-500 transition-colors"><X className="h-4 w-4" strokeWidth={1.5} /></button>}
        {status === "failed" && onRetry && (
          <TooltipProvider><Tooltip><TooltipTrigger asChild>
            <button onClick={onRetry} className="rounded-lg p-1 text-red-400 hover:text-red-600 transition-colors"><RefreshCw className="h-4 w-4" strokeWidth={1.5} /></button>
          </TooltipTrigger>{errorMessage && <TooltipContent side="left"><p className="max-w-[200px]">{errorMessage}</p></TooltipContent>}</Tooltip></TooltipProvider>
        )}
      </div>
    </div>
  );
}
