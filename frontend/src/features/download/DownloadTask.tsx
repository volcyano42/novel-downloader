import { CheckCircle, Loader2, X, XCircle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

type TaskStatus = "downloading" | "completed" | "failed";

interface DownloadTaskProps {
  title: string; status: TaskStatus; progress?: number; errorMessage?: string;
  onCancel?: () => void; onRetry?: () => void; className?: string;
}

const statusConfig: Record<TaskStatus, { label: string; className: string; icon: typeof CheckCircle }> = {
  downloading: { label: "下载中", className: "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10", icon: Loader2 },
  completed: { label: "完成", className: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10", icon: CheckCircle },
  failed: { label: "失败", className: "bg-red-50 text-red-500 dark:bg-red-500/10", icon: XCircle },
};

export function DownloadTask({ title, status, progress = 0, errorMessage, onCancel, onRetry, className }: DownloadTaskProps) {
  const cfg = statusConfig[status]; const Icon = cfg.icon;
  return (
    <div className={cn("flex items-center gap-3 rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl px-4 py-3 shadow-[0_8px_30px_rgb(0,0,0,0.04)]", status === "completed" && "animate-[complete-flash_0.5s_ease-out]", className)}>
      <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">{title}</span>
      <div className="flex items-center gap-2 shrink-0">
        {status === "downloading" && (
          <div className="w-20"><div className="relative h-1.5 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full rounded-full bg-indigo-500 transition-all duration-300" style={{ width: `${progress}%` }} />
            <div className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-white/40 to-transparent" />
          </div></div>
        )}
        <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium", cfg.className)}>
          <Icon className={cn("h-3 w-3", status === "downloading" && "animate-spin")} strokeWidth={2} />{cfg.label}
        </span>
        {status === "downloading" && onCancel && <button onClick={onCancel} className="rounded-full p-1 text-slate-400 hover:text-slate-600 transition-colors" aria-label="取消"><X className="h-[18px] w-[18px]" strokeWidth={1.5} /></button>}
        {status === "failed" && (
          <TooltipProvider><Tooltip><TooltipTrigger asChild>
            <button onClick={onRetry} className="rounded-full p-1 text-red-400 hover:text-red-600 transition-colors" aria-label="重试"><RefreshCw className="h-[18px] w-[18px]" strokeWidth={1.5} /></button>
          </TooltipTrigger>{errorMessage && <TooltipContent side="left"><p className="max-w-[200px]">{errorMessage}</p></TooltipContent>}</Tooltip></TooltipProvider>
        )}
      </div>
    </div>
  );
}

export function DownloadTaskSkeleton() {
  return <div className="flex items-center gap-3 rounded-xl border border-white/20 bg-white/80 px-4 py-3"><div className="h-4 w-2/3 animate-pulse rounded bg-slate-300/60" /><div className="h-5 w-14 animate-pulse rounded-full bg-slate-300/60" /></div>;
}
