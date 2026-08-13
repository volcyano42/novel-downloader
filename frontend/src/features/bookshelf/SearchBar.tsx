import { Search, X, Loader2, Link, BookOpen } from "lucide-react";
import { useState, useEffect, type KeyboardEvent } from "react";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  onSearch: (query: string, filters: SearchFilters) => void;
  platforms?: { id: string; label: string }[];
  engineModes?: string[];
  apiVariants?: Record<string, string[]>;
  platformModes?: Record<string, string[]>;
  loading?: boolean;
  defaultQuery?: string;
}

export interface SearchFilters {
  platform?: string; mode?: string; variant?: string;
}

type SearchTab = "url" | "title";

const MODE_LABELS: Record<string, string> = { browser: "Browser", requests: "Requests", api: "API" };

function ModeSelect({ modes, selected, onSelect, className }: {
  modes: string[]; selected: string; onSelect: (m: string) => void; className?: string;
}) {
  return (
    <Select value={selected} onValueChange={onSelect}>
      <SelectTrigger className={cn("w-[110px] shrink-0", className)}>
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

export function SearchBar({ onSearch, platforms = [], engineModes = [], apiVariants = {}, platformModes = {}, loading, defaultQuery = "" }: SearchBarProps) {
  const [tab, setTab] = useState<SearchTab>("title");
  const [query, setQuery] = useState(defaultQuery);
  const [platform, setPlatform] = useState("all");
  const [mode, setMode] = useState(engineModes[0] ?? "browser");
  const [variant, setVariant] = useState<string | undefined>();

  // 平台切换时自动切换到支持的模式
  useEffect(() => {
    if (!availableModes.includes(mode)) {
      setMode(availableModes[0] ?? "browser");
      setVariant(undefined);
    }
  }, [platform, tab]);

  // 平台选择后，使用该平台支持的模式；全平台用全局列表
  const platModes = platform !== "all" ? (platformModes[platform] ?? engineModes) : engineModes;
  // 标题搜索 + 全部/起点时去掉 API 模式（无 API variant 的平台）
  const hasApiVariant = platform !== "all" ? (apiVariants[platform]?.length ?? 0) > 0 : Object.keys(apiVariants).length > 0;
  const hideApiMode = tab === "title" && !hasApiVariant;
  const availableModes = hideApiMode ? platModes.filter(m => m !== "api") : platModes;
  const effectiveMode = availableModes.includes(mode) ? mode : availableModes[0] ?? "browser";

  const trigger = () => {
    const q = query.trim();
    if (!q) return;
    const m = tab === "url" ? urlEffectiveMode : (hideApiMode ? effectiveMode : mode);
    if (tab === "url") {
      onSearch(q, { mode: m, variant });
    } else {
      onSearch(q, { platform, mode: m, variant });
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") trigger();
  };

  const switchTab = (t: SearchTab) => {
    setTab(t);
    setQuery("");
  };

  // 标题模式 全部/起点 自动切到 browser
  useEffect(() => {
    if (hideApiMode && mode === "api") {
      setMode("browser");
      setVariant(undefined);
    }
  }, [hideApiMode, mode]);

  const clear = () => {
    setQuery("");
  };

  const allPlatforms = [{ id: "all", label: "全平台" } as const, ...platforms.map(p => ({ id: p.id, label: p.label }))];

  const currentPlatform = platform || "all";
  const platformVariants = apiVariants[platform] ?? [];

  // URL 模式：从输入中检测平台
  const urlPlatform = (() => {
    if (tab !== "url") return null;
    if (query.includes("fanqienovel.com") || query.includes("changdunovel.com")) return "fanqie";
    if (query.includes("qidian.com")) return "qidian";
    if (query.includes("qimao.com")) return "qimao";
    if (query.includes("92xs.info")) return "92xs";
    return null;
  })();
  // 纯数字 ID → 按位数推断平台（与后端 id_pattern 一致）
  const urlIdPlatform = (() => {
    if (tab !== "url" || urlPlatform) return null;
    const trimmed = query.trim();
    if (!/^\d+$/.test(trimmed)) return null;
    if (trimmed.length === 19) return "fanqie";
    if (trimmed.length === 10) return "qidian";
    return "qimao";
  })();
  const effectiveUrlPlatform = urlPlatform || urlIdPlatform;
  const urlVariants = effectiveUrlPlatform ? (apiVariants[effectiveUrlPlatform] ?? []) : [];
  const urlPlatModes = effectiveUrlPlatform ? (platformModes[effectiveUrlPlatform] ?? engineModes) : engineModes;
  const urlHasApi = urlVariants.length > 0;
  const urlHideApi = !urlHasApi;
  const urlModes = urlHideApi ? urlPlatModes.filter(m => m !== "api") : urlPlatModes;
  const urlEffectiveMode = urlModes.includes(mode) ? mode : urlModes[0] ?? "browser";

  // URL 模式无 API 时自动切 browser
  useEffect(() => {
    if (tab === "url" && urlHideApi && mode === "api") {
      setMode("browser");
      setVariant(undefined);
    }
  }, [tab, effectiveUrlPlatform, mode]);

  return (
    <div className="flex flex-col gap-3">
      {/* Tab 切换 */}
      <div className="flex gap-1 self-start rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
        <button
          onClick={() => switchTab("url")}
          className={cn(
            "flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-xs font-medium transition-all",
            tab === "url"
              ? "bg-white text-slate-800 shadow-sm dark:bg-slate-700 dark:text-slate-200"
              : "text-slate-500 hover:text-slate-700 dark:text-slate-400",
          )}
        >
          <Link className="h-3.5 w-3.5" strokeWidth={1.5} />
          URL 直达
        </button>
        <button
          onClick={() => switchTab("title")}
          className={cn(
            "flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-xs font-medium transition-all",
            tab === "title"
              ? "bg-white text-slate-800 shadow-sm dark:bg-slate-700 dark:text-slate-200"
              : "text-slate-500 hover:text-slate-700 dark:text-slate-400",
          )}
        >
          <BookOpen className="h-3.5 w-3.5" strokeWidth={1.5} />
          标题搜索
        </button>
      </div>

      {/* URL 模式 */}
      {tab === "url" && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <div className="relative flex-1 min-w-0">
              {loading
                ? <Loader2 className="absolute left-3 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-indigo-500 animate-spin" strokeWidth={1.5} />
                : <Link className="absolute left-3 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-slate-400" strokeWidth={1.5} />
              }
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入小说链接或 ID…"
                className={cn(
                  "w-full rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl py-2.5 pl-10 pr-10 text-sm outline-none transition-shadow focus:ring-2 focus:ring-indigo-500/30",
                  loading ? "text-slate-400" : "text-slate-800 placeholder:text-slate-400",
                )}
              />
              {!loading && query && (
                <button onClick={clear} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  <X className="h-[18px] w-[18px]" strokeWidth={1.5} />
                </button>
              )}
            </div>
            <button
              onClick={trigger}
              disabled={loading || !query.trim()}
              className="rounded-xl bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-600 transition-colors disabled:opacity-50 shrink-0"
            >
              搜索
            </button>
          </div>
          {(urlModes.length > 0 || (urlEffectiveMode === "api" && urlVariants.length > 0)) && (
            <div className="flex flex-wrap items-center gap-2">
              {urlModes.length > 0 && (
                <ModeSelect modes={urlModes} selected={urlEffectiveMode} onSelect={m => { setMode(m); if (m !== "api") setVariant(undefined); }} />
              )}
              {urlEffectiveMode === "api" && urlVariants.length > 0 && (
                <div className="flex items-center gap-1">
                  {urlVariants.map(p => (
                    <button
                      key={p}
                      onClick={() => setVariant(variant === p ? undefined : p)}
                      className={cn(
                        "rounded-lg px-2 py-1 text-[11px] font-medium transition-colors",
                        variant === p ? "bg-indigo-500 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200",
                      )}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 标题模式 */}
      {tab === "title" && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <div className="relative flex-1 min-w-0">
              {loading
                ? <Loader2 className="absolute left-3 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-indigo-500 animate-spin" strokeWidth={1.5} />
                : <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-slate-400" strokeWidth={1.5} />
              }
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="搜索书名、作者…"
                className={cn(
                  "w-full rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl py-2.5 pl-10 pr-10 text-sm outline-none transition-shadow focus:ring-2 focus:ring-indigo-500/30",
                  loading ? "text-slate-400" : "text-slate-800 placeholder:text-slate-400",
                )}
              />
              {!loading && query && (
                <button onClick={clear} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  <X className="h-[18px] w-[18px]" strokeWidth={1.5} />
                </button>
              )}
            </div>
            <button
              onClick={trigger}
              disabled={loading || !query.trim()}
              className="rounded-xl bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-600 transition-colors disabled:opacity-50 shrink-0"
            >
              搜索
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* 平台选择 */}
            <Select value={currentPlatform} onValueChange={v => { setPlatform(v); setVariant(undefined); }}>
              <SelectTrigger className="w-[100px] shrink-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {allPlatforms.map(p => (
                  <SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {availableModes.length > 0 && (
              <ModeSelect modes={availableModes} selected={effectiveMode} onSelect={m => { setMode(m); if (m !== "api") setVariant(undefined); }} />
            )}
            {effectiveMode === "api" && platformVariants.length > 0 && (
              <div className="flex items-center gap-1">
                {platformVariants.map(p => (
                  <button
                    key={p}
                    onClick={() => setVariant(variant === p ? undefined : p)}
                    className={cn(
                      "rounded-lg px-2 py-1 text-[11px] font-medium transition-colors",
                      variant === p ? "bg-indigo-500 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200",
                    )}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
