import {BookOpen, Link, Loader2, Search, X} from "lucide-react";
import {type KeyboardEvent, useEffect, useMemo, useRef, useState} from "react";
import {Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue} from "@/components/ui/select";
import {cn} from "@/lib/utils";
import type {SourceOption} from "@/api/endpoints";

interface SearchBarProps {
  /** 标题搜索并发勾选的书源；URL 直达携带用户手选的单个书源。 */
  onSearch: (query: string, opts?: { source?: string; sources?: string[] }) => void;
  sources?: SourceOption[];
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

  // 勾选集合：null = 未初始化（= 全选）。不持久化、不在 sources 刷新时重置用户选择。
  const [picked, setPicked] = useState<string[] | null>(null);
  const allNames = useMemo(() => sources.map(s => s.name), [sources]);
  const selected = picked ?? allNames;
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  // 分组 → 该组书源（"" 走「未分组」桶，排在最后）
  const groupedSources = useMemo(() => {
    const groups = new Map<string, SourceOption[]>();
    for (const s of sources) {
      if (!groups.has(s.group)) groups.set(s.group, []);
      groups.get(s.group)!.push(s);
    }
    return [...groups.entries()].sort(([a], [b]) => (a === "" ? 1 : b === "" ? -1 : a.localeCompare(b)));
  }, [sources]);

  const toggleAll = () => setPicked(selected.length === allNames.length ? [] : allNames);
  const pickGroup = (group: string) => setPicked(sources.filter(s => s.group === group).map(s => s.name));
  const toggleOne = (name: string) => setPicked(selectedSet.has(name) ? selected.filter(n => n !== name) : [...allNames.filter(n => selectedSet.has(n) || n === name)]);

  const trigger = () => {
    const q = query.trim();
    if (!q) return;
    if (tab === "url") {
      if (!source) {
        setShake(true);
        setTimeout(() => setShake(false), 400);
        return;
      }
      onSearch(q, { source });
    } else {
      // 勾选为空：按钮已 disabled；此处再 guard 一次，防止 Enter 键绕过（spec §6.5：不发请求）
      if (selected.length === 0) return;
      onSearch(q, { sources: selected });
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
                {groupedSources.map(([group, items]) => (
                  <SelectGroup key={group}>
                    <SelectLabel className="px-2 py-1 text-[10px] text-slate-400">{group || "未分组"}</SelectLabel>
                    {items.map(({ name, alias }) => (
                      <SelectItem key={name} value={name}>{alias}</SelectItem>
                    ))}
                  </SelectGroup>
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
              disabled={loading || !query.trim() || selected.length === 0}
              className="rounded-xl bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-600 transition-colors disabled:opacity-50 shrink-0"
            >
              搜索
            </button>
          </div>
          {selected.length === 0 && (
            <p className="px-1 text-[11px] text-red-400">请至少勾选一个书源</p>
          )}
          <div className={cn("flex flex-col gap-2 rounded-xl border border-white/20 bg-white/50 p-2 backdrop-blur-sm dark:border-slate-600/30 dark:bg-slate-800/40",
                             shake && "border-red-300 bg-red-50 animate-shake")}>
            {/* 框 1：批量单选（全选 / 各分组 / 未分组） */}
            <div className="flex flex-wrap items-center gap-1">
              <button onClick={toggleAll}
                className={cn("rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors",
                  selected.length === allNames.length
                    ? "bg-indigo-100 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-300"
                    : "text-slate-500 hover:text-slate-700 dark:text-slate-400")}>
                {selected.length === allNames.length ? "全不选" : "全选"}
              </button>
              {groupedSources.map(([group, items]) => {
                const names = items.map(i => i.name);
                const active = selected.length === names.length && names.every(n => selectedSet.has(n));
                return (
                  <button key={group} onClick={() => pickGroup(group)}
                    className={cn("rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors",
                      active ? "bg-indigo-100 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-300"
                             : "text-slate-500 hover:text-slate-700 dark:text-slate-400")}>
                    {group || "未分组"}
                  </button>
                );
              })}
              <span className="ml-auto text-[11px] text-slate-400">已选 {selected.length}/{allNames.length}</span>
            </div>
            {/* 框 2：逐源复选（显示别名，按分组分节） */}
            <div className="flex flex-col gap-1">
              {groupedSources.map(([group, items]) => (
                <div key={group} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="w-16 shrink-0 truncate text-[10px] text-slate-400">{group || "未分组"}</span>
                  {items.map(s => (
                    <label key={s.name} className="flex cursor-pointer items-center gap-1 text-[11px] text-slate-600 dark:text-slate-300">
                      <input type="checkbox" checked={selectedSet.has(s.name)} onChange={() => toggleOne(s.name)} className="h-3.5 w-3.5 rounded border-slate-300" />
                      <span>{s.alias}</span>
                    </label>
                  ))}
                </div>
              ))}
              {sources.length === 0 && <span className="px-1 text-[11px] text-slate-400">没有可用的书源</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
