import { Search, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SearchResultCardProps {
  title: string; author: string; description: string | null;
  loading?: boolean; onClick?: () => void; className?: string;
}

export function SearchResultCard({ title, author, description, loading, onClick, className }: SearchResultCardProps) {
  return (
    <div
      onClick={loading ? undefined : onClick}
      className={cn(
        "cursor-pointer flex flex-col rounded-2xl border border-indigo-200/40 bg-indigo-50/30 backdrop-blur-sm p-5",
        "hover:border-indigo-300/60 hover:bg-indigo-50/60 hover:-translate-y-0.5 hover:shadow-[0_12px_30px_rgb(99,102,241,0.08)]",
        "transition-all duration-300 ease-out",
        loading && "opacity-60 pointer-events-none",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-100 text-indigo-400">
          {loading ? <Loader2 className="h-[18px] w-[18px] animate-spin" strokeWidth={2} /> : <Search className="h-[18px] w-[18px]" strokeWidth={1.5} />}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-slate-800">{title}</h3>
          <p className="text-sm text-slate-500">{author}</p>
        </div>
      </div>
      {description && (
        <p className="mt-3 line-clamp-2 text-xs text-slate-400 leading-relaxed">{description}</p>
      )}
    </div>
  );
}
