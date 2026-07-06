import { Search, Filter, X } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  onSearch: (query: string, filters: SearchFilters) => void;
  groups?: string[]; formats?: string[]; platforms?: { id: string; label: string }[]; className?: string;
}

export interface SearchFilters { group?: string; format?: string; platform?: string; }

export function SearchBar({ onSearch, groups = [], formats = [], platforms = [], className }: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilters>({});
  const [showFilters, setShowFilters] = useState(false);

  const trigger = (q: string, f: SearchFilters) => onSearch(q, f);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") trigger(query, filters);
  };
  const handleFilterChange = (key: keyof SearchFilters, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value || undefined }));
  };
  const clear = () => { setQuery(""); setFilters({}); onSearch("", {}); };

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center gap-2">
        {platforms.length > 0 && (
          <select
            value={filters.platform ?? platforms[0].id}
            onChange={e => { const v = e.target.value; handleFilterChange("platform", v); }}
            className="rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl px-3 py-2.5 text-sm text-slate-700 outline-none transition-shadow focus:ring-2 focus:ring-indigo-500/30 appearance-none"
          >
            {platforms.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        )}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-slate-400" strokeWidth={1.5} />
          <input type="text" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={handleKeyDown} placeholder="搜索书名、作者..." className="w-full rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl py-2.5 pl-10 pr-10 text-sm text-slate-800 placeholder:text-slate-400 outline-none transition-shadow focus:ring-2 focus:ring-indigo-500/30" />
          {query && <button onClick={clear} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"><X className="h-[18px] w-[18px]" strokeWidth={1.5} /></button>}
        </div>
        <button onClick={() => setShowFilters(!showFilters)} className={cn("rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl p-2.5 text-slate-500 transition-colors", showFilters && "text-indigo-500 border-indigo-500/30")}><Filter className="h-[18px] w-[18px]" strokeWidth={1.5} /></button>
      </div>
      {showFilters && (
        <div className="flex gap-2 animate-in fade-in slide-in-from-top-2 duration-200">
          {groups.length > 0 && <select value={filters.group ?? ""} onChange={(e) => handleFilterChange("group", e.target.value)} className="rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl px-3 py-2 text-sm text-slate-700 outline-none"><option value="">全部分组</option>{groups.map(g => <option key={g} value={g}>{g}</option>)}</select>}
          {formats.length > 0 && <select value={filters.format ?? ""} onChange={(e) => handleFilterChange("format", e.target.value)} className="rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl px-3 py-2 text-sm text-slate-700 outline-none"><option value="">全部格式</option>{formats.map(f => <option key={f} value={f}>{f}</option>)}</select>}
        </div>
      )}
    </div>
  );
}

export function SearchBarSkeleton() {
  return <div className="flex items-center gap-2"><div className="h-10 flex-1 animate-pulse rounded-xl bg-slate-300/60" /><div className="h-10 w-10 animate-pulse rounded-xl bg-slate-300/60" /></div>;
}
