import {BookOpen, Link, Loader2, Search, X} from "lucide-react";
import {type KeyboardEvent, useEffect, useRef, useState} from "react";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {cn} from "@/lib/utils";

interface SearchBarProps {
  /** 标题搜索并发全部启用书源（source 省略）；URL 直达携带用户手选书源。 */
  onSearch: (query: string, source?: string) => void;
  /** 全部书源名（URL tab 手选；标题 tab 不使用） */
  sources?: string[];
  loading?: boolean;
  defaultQuery?: string;
  /** 外部回填（点击搜索历史）：nonce 变化时同步到内部 state，不触发搜索 */
  prefill?: { nonce: number; query: string; source?: string } | null;
}

type SearchTab = "url" | "title";

export function SearchBar({ onSearch, sources = [], loading, defaultQuery = "", prefill }: SearchBarProps) {
  const [tab, setTab] = useState<SearchTab>("title");
  const [query, setQuery] = useState(defaultQuery);
  const [source, setSource] = useState("");
  const [shake, setShake] = useState(false);

  const trigger = () => {
    const q = query.trim();
    if (!q) return;
    if (tab === "url") {
      if (!source) {
        setShake(true);
        setTimeout(() => setShake(false), 400);
        return;
      }
      onSearch(q, source);
    } else {
      onSearch(q);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") trigger();
  };

  const switchTab = (t: SearchTab) => {
    setTab(t);
    setQuery("");
  };

  // 点击搜索历史回填：只在 nonce 变化时同步一次 keyword + source。
  // prefill 是对象、每次渲染可能是新引用，直接入依赖会让用户在输入框打字时被反复覆盖，故用 ref。
  const prefillRef = useRef(prefill);
  prefillRef.current = prefill;
  useEffect(() => {
    const p = prefillRef.current;
    if (!p) return;
    setQuery(p.query);
    setSource(p.source ?? "");
  }, [prefill?.nonce]);

  const clear = () => {
    setQuery("");
  };

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
          <div className={cn("flex flex-wrap items-center gap-2 rounded-lg px-1.5 py-1 transition-colors", shake && "border border-red-300 bg-red-50 animate-shake")}>
            <span className="text-[11px] text-slate-400">书源</span>
            <Select value={source} onValueChange={setSource}>
              <SelectTrigger className="w-[180px] shrink-0">
                <SelectValue placeholder="选择书源" />
              </SelectTrigger>
              <SelectContent>
                {sources.map(name => (
                  <SelectItem key={name} value={name}>{name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-[11px] text-slate-400">URL 解析需指定书源（无自动推断）</span>
          </div>
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
          <p className="px-1 text-[11px] text-slate-400">并发搜索全部已启用书源</p>
        </div>
      )}
    </div>
  );
}
