import { Search, Filter, X, Loader2, ChevronDown, ChevronRight } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  onSearch: (query: string, filters: SearchFilters) => void;
  groups?: string[]; formats?: string[]; platforms?: { id: string; label: string }[];
  engineModes?: string[]; apiProviders?: Record<string, string[]>;
  loading?: boolean; className?: string;
}

export interface SearchFilters {
  group?: string; format?: string; platform?: string; mode?: string; provider?: string;
}

const MODE_LABELS: Record<string, string> = { browser: "Browser", requests: "Requests", api: "API" };

export function SearchBar({ onSearch, groups = [], formats = [], platforms = [], engineModes = [], apiProviders = {}, loading, className }: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilters>({});
  const [showFilters, setShowFilters] = useState(false);
  const [platformOpen, setPlatformOpen] = useState(false);
  const [modeOpen, setModeOpen] = useState(false);
  const [subOpen, setSubOpen] = useState(false);

  const trigger = (q: string, f: SearchFilters) => onSearch(q, f);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") trigger(query, filters);
  };
  const setFilter = (key: keyof SearchFilters, value: string | undefined) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };
  const clear = () => { setQuery(""); setFilters({}); onSearch("", {}); };

  const currentPlatform = filters.platform ?? platforms[0]?.id ?? "";
  const currentMode = filters.mode ?? engineModes[0] ?? "";
  const platformProviders = apiProviders[currentPlatform] ?? [];

  const selectMode = (m: string) => {
    setFilter("mode", m);
    if (m !== "api") { setFilter("provider", undefined); setModeOpen(false); }
  };

  const selectProvider = (p: string) => {
    setFilter("provider", p);
    setModeOpen(false); setSubOpen(false);
  };

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center gap-2">
        {platforms.length > 0 && (
          <div className="relative" onMouseLeave={() => setPlatformOpen(false)}>
            <button onClick={() => setPlatformOpen(!platformOpen)}
              className="flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl px-3 py-2.5 text-sm text-slate-700 outline-none transition-shadow focus:ring-2 focus:ring-indigo-500/30">
              {platforms.find(p => p.id === currentPlatform)?.label ?? currentPlatform}
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" strokeWidth={1.5} />
            </button>
            {platformOpen && (
              <div className="absolute top-full left-0 mt-1 z-50 rounded-xl border border-white/20 bg-white/95 backdrop-blur-xl shadow-lg py-1 min-w-[120px] dark:bg-slate-900/95 dark:border-slate-700/30">
                {platforms.map(p => (
                  <button key={p.id} onClick={() => { setFilter("platform", p.id); setFilter("provider", undefined); setFilter("mode", undefined); setPlatformOpen(false); }}
                    className={cn("w-full px-4 py-2 text-sm text-left transition-colors",
                      currentPlatform === p.id ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-400" : "text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800/50")}>
                    {p.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {engineModes.length > 0 && (
          <div className="relative" onMouseLeave={() => { setModeOpen(false); setSubOpen(false); }}>
            <button onClick={() => setModeOpen(!modeOpen)}
              className="flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl px-3 py-2.5 text-sm text-slate-700 outline-none transition-shadow focus:ring-2 focus:ring-indigo-500/30">
              {currentMode === "api" && filters.provider ? `API:${filters.provider}` : MODE_LABELS[currentMode] ?? currentMode}
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" strokeWidth={1.5} />
            </button>
            {modeOpen && (
              <div className="absolute top-full left-0 mt-1 z-50 rounded-xl border border-white/20 bg-white/95 backdrop-blur-xl shadow-lg py-1 min-w-[120px] dark:bg-slate-900/95 dark:border-slate-700/30">
                {engineModes.map(m => {
                  const hasSub = m === "api" && platformProviders.length > 0;
                  return (
                    <div key={m} className="relative" onMouseEnter={() => hasSub && setSubOpen(true)} onMouseLeave={() => setSubOpen(false)}>
                      <button onClick={() => selectMode(m)}
                        className={cn("w-full flex items-center justify-between px-4 py-2 text-sm text-left transition-colors",
                          currentMode === m ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-400" : "text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800/50")}>
                        {MODE_LABELS[m] ?? m}
                        {hasSub && <ChevronRight className="h-3.5 w-3.5 text-slate-400" strokeWidth={1.5} />}
                      </button>
                      {hasSub && subOpen && (
                        <div className="absolute left-full top-0 ml-0.5 z-50 rounded-xl border border-white/20 bg-white/95 backdrop-blur-xl shadow-lg py-1 min-w-[100px] dark:bg-slate-900/95 dark:border-slate-700/30">
                          {platformProviders.map(p => (
                            <button key={p} onClick={() => selectProvider(p)}
                              className={cn("w-full px-4 py-2 text-sm text-left transition-colors whitespace-nowrap",
                                filters.provider === p ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-400" : "text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800/50")}>
                              {p}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <div className="relative flex-1">
          {loading ? <Loader2 className="absolute left-3 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-indigo-500 animate-spin" strokeWidth={1.5} /> : <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-slate-400" strokeWidth={1.5} />}
          <input type="text" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={handleKeyDown} placeholder="搜索书名、作者..." disabled={loading} className={cn("w-full rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl py-2.5 pl-10 pr-10 text-sm outline-none transition-shadow focus:ring-2 focus:ring-indigo-500/30", loading ? "text-slate-400" : "text-slate-800 placeholder:text-slate-400")} />
          {!loading && query && <button onClick={clear} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"><X className="h-[18px] w-[18px]" strokeWidth={1.5} /></button>}
        </div>
        <button onClick={() => setShowFilters(!showFilters)} className={cn("rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl p-2.5 text-slate-500 transition-colors", showFilters && "text-indigo-500 border-indigo-500/30")}><Filter className="h-[18px] w-[18px]" strokeWidth={1.5} /></button>
      </div>
      {showFilters && (
        <div className="flex gap-2 animate-in fade-in slide-in-from-top-2 duration-200">
          {groups.length > 0 && <select value={filters.group ?? ""} onChange={(e) => setFilter("group", e.target.value || undefined)} className="rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl px-3 py-2 text-sm text-slate-700 outline-none"><option value="">全部分组</option>{groups.map(g => <option key={g} value={g}>{g}</option>)}</select>}
          {formats.length > 0 && <select value={filters.format ?? ""} onChange={(e) => setFilter("format", e.target.value || undefined)} className="rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl px-3 py-2 text-sm text-slate-700 outline-none"><option value="">全部格式</option>{formats.map(f => <option key={f} value={f}>{f}</option>)}</select>}
        </div>
      )}
    </div>
  );
}

export function SearchBarSkeleton() {
  return <div className="flex items-center gap-2"><div className="h-10 flex-1 animate-pulse rounded-xl bg-slate-300/60" /><div className="h-10 w-10 animate-pulse rounded-xl bg-slate-300/60" /></div>;
}
