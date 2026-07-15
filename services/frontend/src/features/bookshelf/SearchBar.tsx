import { Search, Filter, X, Loader2 } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  onSearch: (query: string, filters: SearchFilters) => void;
  groups?: string[]; formats?: string[]; platforms?: { id: string; label: string }[];
  engineModes?: string[]; apiProviders?: Record<string, string[]>;
  loading?: boolean; className?: string;
  defaultQuery?: string; defaultPlatform?: string;
}

export interface SearchFilters {
  group?: string; format?: string; platform?: string; mode?: string; provider?: string;
}

const MODE_LABELS: Record<string, string> = { browser: "Browser", requests: "Requests", api: "API" };

// ── sub-components ──

function PlatformSelect({ platforms, selected, onSelect, className }: {
  platforms: { id: string; label: string }[]; selected: string; onSelect: (id: string) => void; className?: string;
}) {
  return (
    <Select value={selected} onValueChange={onSelect}>
      <SelectTrigger className={cn(className?.includes("flex-1") ? "w-full" : "w-[120px]")}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {platforms.map(p => (
          <SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function ModeSelect({ modes, selected, onSelect, className }: {
  modes: string[]; selected: string; onSelect: (m: string) => void; className?: string;
}) {
  return (
    <Select value={selected} onValueChange={onSelect}>
      <SelectTrigger className={cn(className?.includes("flex-1") ? "w-full" : "w-[120px]")}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {modes.map(m => (
          <SelectItem key={m} value={m}>{MODE_LABELS[m] ?? m}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

// ── main ──

export function SearchBar({ onSearch, groups = [], formats = [], platforms = [], engineModes = [], apiProviders = {}, loading, className, defaultQuery = "", defaultPlatform }: SearchBarProps) {
  const [query, setQuery] = useState(defaultQuery);
  const [filters, setFilters] = useState<SearchFilters>(
    defaultPlatform ? { platform: defaultPlatform } : {}
  );
  const [showFilters, setShowFilters] = useState(false);

  const trigger = (q: string, f: SearchFilters) => onSearch(q, f);
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => { if (e.key === "Enter") trigger(query, filters); };
  const setFilter = (key: keyof SearchFilters, value: string | undefined) => setFilters(prev => ({ ...prev, [key]: value }));
  const clear = () => { setQuery(""); setFilters({}); onSearch("", {}); };

  const currentPlatform = filters.platform ?? platforms[0]?.id ?? "";
  const currentMode = filters.mode ?? engineModes[0] ?? "";
  const platformProviders = apiProviders[currentPlatform] ?? [];

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {/* mobile: selectors row */}
      {(platforms.length > 0 || engineModes.length > 0) && (
        <div className="flex items-center gap-2 md:hidden">
          {platforms.length > 0 && (
            <PlatformSelect platforms={platforms} selected={currentPlatform}
              onSelect={id => { setFilter("platform", id); setFilter("provider", undefined); setFilter("mode", undefined); }}
              className="flex-1" />
          )}
          {engineModes.length > 0 && (
            <ModeSelect modes={engineModes} selected={currentMode}
              onSelect={m => { setFilter("mode", m); if (m !== "api") setFilter("provider", undefined); }}
              className="flex-1" />
          )}
          {currentMode === "api" && platformProviders.length > 0 && platformProviders.map(p => (
            <button key={p} onClick={() => setFilter("provider", filters.provider === p ? undefined : p)}
              className={cn("rounded-lg px-2 py-1 text-[11px] font-medium transition-colors", filters.provider === p ? "bg-indigo-500 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200")}>{p}</button>
          ))}
        </div>
      )}

      {/* search row */}
      <div className="flex items-center gap-2">
        {platforms.length > 0 && (
          <PlatformSelect platforms={platforms} selected={currentPlatform}
            onSelect={id => { setFilter("platform", id); setFilter("provider", undefined); setFilter("mode", undefined); }}
            className="hidden md:block" />
        )}
        {engineModes.length > 0 && (
          <div className="hidden md:flex items-center gap-1.5">
            <ModeSelect modes={engineModes} selected={currentMode}
              onSelect={m => { setFilter("mode", m); if (m !== "api") setFilter("provider", undefined); }} />
            {currentMode === "api" && platformProviders.length > 0 && platformProviders.map(p => (
              <button key={p} onClick={() => setFilter("provider", filters.provider === p ? undefined : p)}
                className={cn("rounded-lg px-2 py-1 text-[11px] font-medium transition-colors", filters.provider === p ? "bg-indigo-500 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200")}>{p}</button>
            ))}
          </div>
        )}
        <div className="relative flex-1">
          {loading ? <Loader2 className="absolute left-3 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-indigo-500 animate-spin" strokeWidth={1.5} /> : <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-slate-400" strokeWidth={1.5} />}
          <input type="text" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={handleKeyDown} placeholder="搜索书名、作者..." className={`w-full rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl py-2.5 pl-10 pr-10 text-sm outline-none transition-shadow focus:ring-2 focus:ring-indigo-500/30 ${loading ? "text-slate-400" : "text-slate-800 placeholder:text-slate-400"}`} />
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
