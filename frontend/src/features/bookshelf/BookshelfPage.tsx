import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {useNavigate} from "react-router-dom";
import {ChevronDown, Heart} from "lucide-react";
import {cn} from "@/lib/utils";
import {BookCard, BookCardSkeleton} from "./BookCard";
import {SearchBar} from "./SearchBar";
import {SearchHistoryPanel} from "./SearchHistoryPanel";
import {SearchResultCard} from "./SearchResultCard";
import {DownloadTask, DownloadTaskSkeleton} from "@/features/download/DownloadTask";
import {SettingsView} from "@/features/settings/SettingsPage";
import {useToast} from "@/components/toast-context";
import {
  useAddSearchHistory,
  useDeleteNovel,
  useFavorites,
  useFetchMeta,
  useGlobalConfig,
  useGroups,
  useNovels,
  useSearch,
  useSources,
  useTasks
} from "@/hooks/index";
import {coverToUrl, deleteTask, type NovelMeta, pauseTask, resumeTask, type SearchResult, toSourceOptions} from "@/api/endpoints";
import {SessionCache} from "@/utils/sessionCache";
import {notifyUser} from "@/utils/notify";

type NavItem = "bookshelf" | "downloads" | "settings" | "search";

export default function BookshelfPage() {
  const pathname = window.location.pathname;
  const activeNav: NavItem = useMemo(() => {
    if (pathname === "/downloads") return "downloads";
    if (pathname === "/settings") return "settings";
    if (pathname === "/search-tab") return "search";
    return "bookshelf";
  }, [pathname]);

  // hooks
  const { data: novels = [], isLoading: loadingNovels, refetch: refetchNovels } = useNovels();
  const { data: globalConfig } = useGlobalConfig();
  const { data: groups = {} } = useGroups();
  const { data: favorites = [] } = useFavorites();
  const { data: tasks = [], isLoading: tasksLoading } = useTasks(activeNav === "downloads");
  const toast = useToast();
  const deleteNovelMut = useDeleteNovel();
  const fetchMetaMut = useFetchMeta();
  const addHistoryMut = useAddSearchHistory();

  // 全部书源名（URL 直达手选 + 结果分组）
  const { data: sources } = useSources();
  const sourceNames = useMemo(() => (sources ? Object.keys(sources) : []), [sources]);
  const sourceOptions = useMemo(() => toSourceOptions(sources), [sources]);

  // local state
  const searchQuery = "";
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [navigatingId, setNavigatingId] = useState<string | null>(null);
  const navigatingRef = useRef(false);
  const [searchCachedQuery, setSearchCachedQuery] = useState("");
  const [prefill, setPrefill] = useState<{ nonce: number; query: string; source?: string } | null>(null);
  const [resultTab, setResultTab] = useState<string>("all");
  const navigate = useNavigate();

  // search — using React Query
  const [searchParams, setSearchParams] = useState<{
    query: string; source?: string;
  } | null>(null);
  const { data: searchResults = [], isFetching: searching, error: searchError } = useSearch(searchParams);

  // 切回搜索 tab 时恢复上次搜索 UI 状态（不自动搜索）
  useEffect(() => {
    if (activeNav !== "search") return;
    const cached = SessionCache.getSearchParams();
    if (cached) setSearchCachedQuery(cached.query);
  }, [activeNav]);

  // tasks notification
  const prevTaskRef = useRef<Record<string, string>>({});
  useEffect(() => {
    const prev = prevTaskRef.current;
    const sound = globalConfig?.notify?.sound ?? "bell";
    for (const t of tasks) {
      const wasDownloading = prev[t.task_id] === "downloading";
      if ((t.status === "completed" || t.status === "partial") && wasDownloading) {
        toast(`「${t.title}」下载完成`, "success");
        notifyUser(sound, `「${t.title}」下载完成`);
        refetchNovels();
      } else if (t.status === "failed" && wasDownloading) {
        toast(`「${t.title}」下载失败${t.error ? "：" + t.error : ""}`, "error");
        notifyUser(sound, `「${t.title}」下载失败`);
        refetchNovels();
      }
      prev[t.task_id] = t.status;
    }
  }, [tasks, toast, refetchNovels, globalConfig?.notify?.sound]);


  const handleOnlineSearch = useCallback(async (query: string, source?: string) => {
    if (!query.trim()) { setSearchParams(null); SessionCache.clearSearch(); return; }
    SessionCache.saveSearch(query, source);
    addHistoryMut.mutate({ source_name: source ?? "", keyword: query.trim() });

    const isUrlOrId = query.startsWith("http://") || query.startsWith("https://") || /^\d+$/.test(query);
    if (isUrlOrId) {
      if (!source) { toast("URL 直达需选择书源"); return; }
      try {
        const meta = await fetchMetaMut.mutateAsync({ url: query, source });
        navigate(`/search/${meta.id}`, { state: { remoteUrl: query, source, meta } });
      } catch (e: unknown) { toast((e as Error).message || "获取小说信息失败"); }
      return;
    }
    setSearchParams({ query, source });
  }, [navigate, toast, fetchMetaMut, addHistoryMut]);

  const handleHistoryPick = useCallback((item: { source_name: string; keyword: string }) => {
    setPrefill({ nonce: Date.now(), query: item.keyword, source: item.source_name || undefined });
  }, []);

  const handleGoToNovel = useCallback(async (result: SearchResult) => {
    if (navigatingRef.current) return;
    navigatingRef.current = true;
    setNavigatingId(result.url);
    const source = result.source_name;
    const idMatch = result.url.match(/\/(page|book|info|shuku)\/(\d+)/);
    const maybeId = idMatch ? idMatch[2] : null;
    const local = maybeId ? novels.find(n => n.id === maybeId) : undefined;
    if (local) {
      navigate(`/search/${local.id}`, { state: { remoteUrl: result.url, source, meta: local } });
      return;
    }
    try {
      const meta = await fetchMetaMut.mutateAsync({ url: result.url, source });
      navigate(`/search/${meta.id}`, { state: { remoteUrl: result.url, source, meta } });
    } catch (e: unknown) { toast((e as Error).message || "获取小说信息失败"); setNavigatingId(null); navigatingRef.current = false; }
  }, [navigate, novels, fetchMetaMut, toast]);

  const handleSettingsUpdate = useCallback((_path: string, _value: unknown) => {
    // 配置已在 SettingsView 内部通过 React Query 自动保存
  }, []);

  // groups
  const groupNames = useMemo(() => Object.keys(groups), [groups]);
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);

  const handleDeleteNovel = useCallback((novelId: string) => {
    deleteNovelMut.mutate(novelId);
  }, [deleteNovelMut]);


  return (
    <>
      {activeNav === "bookshelf" && (
        <div className="mx-auto max-w-[1440px] space-y-6 px-6 pt-12 pb-8 md:px-12">
          {loadingNovels ? (
            <div className="grid grid-cols-3 gap-5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7">{Array.from({ length: 6 }).map((_, i) => <BookCardSkeleton key={i} />)}</div>
          ) : (() => {
            const filtered = (showFavoritesOnly
              ? novels.filter(n => favorites.includes(n.id))
              : novels).filter(n =>
                !searchQuery || n.title.includes(searchQuery) || n.author.includes(searchQuery)
              );
            return (
              <div className="space-y-6">
                <div className="flex items-center gap-3">
                  <button onClick={() => setShowFavoritesOnly(false)}
                    className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                      !showFavoritesOnly ? "bg-indigo-100 text-indigo-600" : "text-slate-500 hover:text-slate-700"
                    }`}>全部</button>
                  <button onClick={() => setShowFavoritesOnly(true)}
                    className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors flex items-center gap-1.5 ${
                      showFavoritesOnly ? "bg-rose-100 text-rose-500" : "text-slate-500 hover:text-slate-700"
                    }`}>
                    <Heart className="h-3.5 w-3.5" fill={showFavoritesOnly ? "currentColor" : "none"} />收藏
                  </button>
                </div>
                {filtered.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-20 text-slate-400"><p className="text-lg">{searchQuery ? "无匹配结果" : showFavoritesOnly ? "暂无收藏" : "书架空空"}</p></div>
                ) : (() => {
                  const groupMap = new Map<string, string>();
                  for (const [group, ids] of Object.entries(groups)) {
                    for (const id of Object.keys(ids)) groupMap.set(id, group);
                  }
                  const grouped = new Map<string, NovelMeta[]>();
                  const ungrouped: NovelMeta[] = [];
                  for (const n of filtered) {
                    const g = groupMap.get(n.id);
                    if (g) { if (!grouped.has(g)) grouped.set(g, []); grouped.get(g)!.push(n); }
                    else ungrouped.push(n);
                  }
                  const entries = [...grouped.entries(), ...(ungrouped.length ? [["未分类", ungrouped] as const] : [])];
                  const toggleGroup = (tag: string) => setCollapsed(prev => {
                    const next = new Set(prev);
                    if (next.has(tag)) next.delete(tag); else next.add(tag);
                    return next;
                  });
                  return (
                    <div className="space-y-6">
                      {entries.map(([tag, items]) => (
                        <div key={tag}>
                          <button onClick={() => toggleGroup(tag)} className="flex items-center gap-2 mb-3 group">
                            <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform duration-200 ${collapsed.has(tag) ? "-rotate-90" : ""}`} strokeWidth={1.5} />
                            <span className="text-sm font-medium text-slate-600">{tag}</span>
                            <span className="text-xs text-slate-400">({items.length})</span>
                          </button>
                          {!collapsed.has(tag) && (
                            <div className="grid grid-cols-3 gap-5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7">
                              {items.map(novel => (
                                <BookCard key={novel.id} novelId={novel.id} title={novel.title} author={novel.author}
                                  sourceName={novel.source_name}
                                  onRead={() => navigate(`/novel/${novel.id}`)}
                                  groups={groupNames}
                                  currentGroup={tag === "未分类" ? undefined : tag}
                                  onDelete={handleDeleteNovel}
                                  cover={coverToUrl(novel.cover)}
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </div>
            );
          })()}
        </div>
      )}

      {activeNav === "downloads" && (
        <div className="mx-auto max-w-[720px] space-y-2 px-6 pt-12 pb-8 md:px-12">
          {tasksLoading ? (
            <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <DownloadTaskSkeleton key={i} />)}</div>
          ) : tasks.length === 0 ? <p className="text-center text-sm text-slate-400 py-20">暂无下载任务</p>
            : [...tasks].reverse().map(task => {
              const pct = task.total > 0 ? Math.round((task.progress / task.total) * 100) : 0;
              const status = task.status as "queued" | "downloading" | "paused" | "completed" | "failed" | "partial" | "cancelled";
              return (
                <DownloadTask key={task.task_id} title={task.title}
                  status={status} progress={pct} errorMessage={task.error ?? undefined}
                  currentTitle={task.current_title} chapters={task.chapters}
                  sourceName={task.source_name} createdAt={task.created_at}
                  onPause={() => pauseTask(task.task_id)}
                  onResume={() => resumeTask(task.task_id)}
                  onCancel={() => deleteTask(task.task_id)}
                  onRetry={() => resumeTask(task.task_id)} />
              );
            })}
        </div>
      )}

      {activeNav === "search" && (
        <div className="mx-auto max-w-[1440px] space-y-6 px-6 pt-12 pb-8 md:px-12">
          <SearchBar onSearch={handleOnlineSearch} sources={sourceOptions} loading={searching} defaultQuery={searchCachedQuery} prefill={prefill} />
          {!searchParams && !searching && (
            <SearchHistoryPanel onPick={handleHistoryPick} />
          )}
          {searchParams && searchResults.length === 0 && !searching && (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400">
              {searchError ? (
                <>
                  <p className="text-sm text-red-400">搜索失败：{searchError.message}</p>
                  <p className="mt-1 text-xs text-slate-300">请检查书源配置</p>
                </>
              ) : (
                <>
                  <p className="text-sm">未找到相关小说</p>
                  <p className="mt-1 text-xs text-slate-300">试试换个关键词</p>
                </>
              )}
            </div>
          )}
          {searchResults.length > 0 && (() => {
            // 并发搜索（未指定书源）时结果跨多个书源，按 source_name 分组 tab
            const showSourceTabs = !searchParams?.source && sourceNames.length > 0;
            const SOURCE_TABS = [
              { id: "all", label: "全部" },
              ...sourceNames.map(name => ({ id: name, label: name })),
            ];
            const grouped = showSourceTabs && resultTab !== "all" ? searchResults.filter(r => r.source_name === resultTab) : searchResults;
            const counts: Record<string, number> = { all: searchResults.length, ...Object.fromEntries(sourceNames.map(name => [name, searchResults.filter(r => r.source_name === name).length])) };
            const activeTab = showSourceTabs ? resultTab : "all";
            return (
              <>
                {showSourceTabs && (
                  <div className="flex flex-wrap gap-1 self-start rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
                    {SOURCE_TABS.map(t => (
                      <button key={t.id} onClick={() => setResultTab(t.id)}
                        className={cn(
                          "rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
                          activeTab === t.id
                            ? "bg-white text-slate-800 shadow-sm dark:bg-slate-700 dark:text-slate-200"
                            : "text-slate-500 hover:text-slate-700 dark:text-slate-400",
                        )}>
                        {t.label}{` (${counts[t.id]})`}
                      </button>
                    ))}
                  </div>
                )}
                <div className="grid grid-cols-1 gap-3">
                  {grouped.map((r, i) => (
                    <SearchResultCard key={i} title={r.title} author={r.author} description={r.description} cover={r.cover_url} rating={r.extra?.rating} loading={navigatingId === r.url} onClick={() => handleGoToNovel(r)} />
                  ))}
                </div>
              </>
            );
          })()}
        </div>
      )}

      {activeNav === "settings" && globalConfig && (
        <div className="px-6 pt-12 pb-8 md:px-12">
          <SettingsView globalConfig={globalConfig} onUpdate={handleSettingsUpdate} />
        </div>
      )}
    </>
  );
}
