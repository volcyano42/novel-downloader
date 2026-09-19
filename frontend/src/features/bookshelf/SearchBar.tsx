import {BookOpen, Link, Loader2, Search, X} from "lucide-react";
import {type KeyboardEvent, useEffect, useRef, useState} from "react";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {cn} from "@/lib/utils";

interface SearchBarProps {
  onSearch: (query: string, filters: SearchFilters) => void;
  platforms?: { id: string; label: string }[];
  engineModes?: string[];
  platformModes?: Record<string, string[]>;
  loading?: boolean;
  defaultQuery?: string;
  /** 外部回填（点击搜索历史）：nonce 变化时同步到内部 state，不触发搜索 */
  prefill?: { nonce: number; query: string; platform?: string; mode?: string; variant?: string } | null;
  /** platform → mode → variants（browser/requests 也有 variant，如 default） */
  modeVariants?: Record<string, Record<string, string[]>>;
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

export function SearchBar({ onSearch, platforms = [], engineModes = [], platformModes = {}, loading, defaultQuery = "", prefill, modeVariants = {} }: SearchBarProps) {
  const [tab, setTab] = useState<SearchTab>("title");
  const [query, setQuery] = useState(defaultQuery);
  const [platform, setPlatform] = useState("all");
  const [mode, setMode] = useState(engineModes[0] ?? "browser");
  const [variant, setVariant] = useState<string | undefined>();
  const [shakeVariant, setShakeVariant] = useState(false);

  // 平台选择后，使用该平台支持的模式；全平台用全局列表
  const platModes = platform !== "all" ? (platformModes[platform] ?? engineModes) : engineModes;
  // 标题搜索 + 全部/起点时去掉 API 模式（无 API variant 的平台）
  const hasApiVariant = platform !== "all" ? (modeVariants[platform]?.["api"]?.length ?? 0) > 0 : Object.keys(modeVariants).length > 0;
  const hideApiMode = tab === "title" && !hasApiVariant;
  const availableModes = hideApiMode ? platModes.filter(m => m !== "api") : platModes;
  const effectiveMode = availableModes.includes(mode) ? mode : availableModes[0] ?? "browser";

  // 平台/标签切换时，若当前模式不再可用则回退到第一个可用模式。
  // availableModes 每次渲染都是新数组、不能直接入依赖，故用 ref 读取最新值，
  // 以保持原触发时机（依赖 mode 会与下面「URL 模式无 API 时切 browser」的 effect 互相覆盖）。
  const latestModesRef = useRef({ availableModes, mode });
  latestModesRef.current = { availableModes, mode };
  useEffect(() => {
    const { availableModes: modes, mode: current } = latestModesRef.current;
    if (!modes.includes(current)) {
      setMode(modes[0] ?? "browser");
      setVariant(undefined);
    }
  }, [platform, tab]);

  const trigger = () => {
    const q = query.trim();
    if (!q) return;
    const m = tab === "url" ? urlEffectiveMode : (hideApiMode ? effectiveMode : mode);
    // 多 variant 未选 → 整块抖动并拦截（单 variant 自动选，不校验）
    const variants = tab === "url" ? urlVariants : platformVariants;
    const effectiveVariant = variant ?? (variants.length === 1 ? variants[0] : undefined);
    if (variants.length > 1 && !variant) {
      setShakeVariant(true);
      setTimeout(() => setShakeVariant(false), 400);
      return;
    }
    if (tab === "url") {
      onSearch(q, { mode: m, variant: effectiveVariant });
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

  // 点击搜索历史回填：只在 nonce 变化时同步一次 keyword + platform + mode + variant
  // （mode 为空默认 requests）。prefill 是对象、每次渲染可能是新引用，直接入依赖
  // 会让用户在输入框打字时被反复覆盖，故用 ref 读取最新值。
  const prefillRef = useRef(prefill);
  prefillRef.current = prefill;
  useEffect(() => {
    const p = prefillRef.current;
    if (!p) return;
    setQuery(p.query);
    if (p.platform) setPlatform(p.platform);
    setMode(p.mode || "requests");
    // 始终同步 variant：历史条目的 variant 为空时清空，避免残留上一次选择的
    // 变体（如 fanqie api 的 rain）与回填的 platform/mode 不匹配
    setVariant(p.variant || undefined);
  }, [prefill?.nonce]);

  const clear = () => {
    setQuery("");
  };

  const allPlatforms = [{ id: "all", label: "全平台" } as const, ...platforms.map(p => ({ id: p.id, label: p.label }))];

  const currentPlatform = platform || "all";
  const platformVariants = modeVariants[platform]?.[effectiveMode] ?? [];

  // URL 模式：从输入中检测平台
  const urlPlatform = (() => {
    if (tab !== "url") return null;
    if (query.includes("fanqienovel.com") || query.includes("changdunovel.com")) return "fanqie";
    if (query.includes("qidian.com")) return "qidian";
    if (query.includes("qimao.com")) return "qimao";
    if (query.includes("92xs.info")) return "92xs";
    return null;
  })();
  const effectiveUrlPlatform = urlPlatform;
  const urlVariantsByMode = effectiveUrlPlatform ? (modeVariants[effectiveUrlPlatform] ?? {}) : {};
  const urlPlatModes = effectiveUrlPlatform ? (platformModes[effectiveUrlPlatform] ?? engineModes) : engineModes;
  const urlHasApi = (urlVariantsByMode["api"] ?? []).length > 0;
  const urlHideApi = !urlHasApi;
  const urlModes = urlHideApi ? urlPlatModes.filter(m => m !== "api") : urlPlatModes;
  const urlEffectiveMode = urlModes.includes(mode) ? mode : urlModes[0] ?? "browser";
  const urlVariants = urlVariantsByMode[urlEffectiveMode] ?? [];

  // URL 模式无 API 时自动切 browser；urlHideApi 是布尔值，可安全入依赖
  useEffect(() => {
    if (tab === "url" && urlHideApi && mode === "api") {
      setMode("browser");
      setVariant(undefined);
    }
  }, [tab, effectiveUrlPlatform, mode, urlHideApi]);

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
          {urlModes.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <ModeSelect modes={urlModes} selected={urlEffectiveMode} onSelect={m => { setMode(m); if (m !== "api") setVariant(undefined); }} />
            </div>
          )}
          {urlVariants.length > 1 && (
            <div className={cn("rounded-lg px-1.5 py-1 transition-colors", shakeVariant && "border border-red-300 bg-red-50 animate-shake")}>
              <p className="text-[11px] text-slate-400 mb-1">{urlEffectiveMode === "api" ? "选择提供商" : "选择变体"}</p>
              <div className="flex flex-wrap items-center gap-1">
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
          </div>
          {platformVariants.length > 1 && (
            <div className={cn("rounded-lg px-1.5 py-1 transition-colors", shakeVariant && "border border-red-300 bg-red-50 animate-shake")}>
              <p className="text-[11px] text-slate-400 mb-1">{effectiveMode === "api" ? "选择提供商" : "选择变体"}</p>
              <div className="flex flex-wrap items-center gap-1">
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
            </div>
          )}
        </div>
      )}
    </div>
  );
}
