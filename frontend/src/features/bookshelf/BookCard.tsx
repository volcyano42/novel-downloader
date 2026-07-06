import { BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

interface BookCardProps {
  title: string; author: string; novelId?: string; cover?: string; progress?: number;
  onRead?: () => void; className?: string;
}

export function BookCard({ title, author, novelId, cover, progress = 0, onRead, className }: BookCardProps) {
  return (
    <div className={cn("cursor-pointer flex flex-col rounded-2xl border border-white/20 bg-white/80 backdrop-blur-xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-[0_20px_40px_rgb(0,0,0,0.06)] hover:-translate-y-0.5 transition-all duration-300 ease-out", className)}
      onClick={onRead}>
      <div className="aspect-[4/5] overflow-hidden rounded-t-2xl bg-slate-100 p-[25%]">
        {cover ? <img src={cover} alt={title} className="h-full w-full object-contain" loading="lazy" />
        : <div className="flex h-full items-center justify-center"><BookOpen className="h-10 w-10 text-slate-300" strokeWidth={1.5} /></div>}
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
