import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Heart } from "lucide-react";
import { cn } from "@/lib/utils";
import { BookCard, BookCardSkeleton } from "./BookCard";
import { SearchBar } from "./SearchBar";
import { SearchResultCard } from "./SearchResultCard";
import { DownloadTask } from "@/features/download/DownloadTask";
import { SettingsView } from "@/features/settings/SettingsPage";
import { useToast } from "@/components/Toast";
import { useNovels, useGlobalConfig, useSaveGlobalConfig, useGroups, usePlatforms, useSources, useTasks, useSearch, useDeleteNovel, useFetchMeta, useFavorites } from "@/hooks/index";
import { coverToUrl, type NovelMeta, type SearchResult } from "@/api/endpoints";
import { pauseTask, resumeTask, deleteTask } from "@/api/endpoints";
import { SessionCache } from "@/utils/sessionCache";
import { notifyUser } from "@/utils/notify";

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
  const { data: platforms = [] } = usePlatforms();
  const { data: tasks = [] } = useTasks(activeNav === "downloads");
  const toast = useToast();
  const deleteNovelMut = useDeleteNovel();
  const saveGlobalConfigMut = useSaveGlobalConfig();
  const fetchMetaMut = useFetchMeta();

  // sources capabilities for SearchBar
  const { data: sources } = useSources();
  const apiVariants = useMemo(() => {
    const map: Record<string, string[]> = {};
    if (sources) {
      for (const [name, info] of Object.entries(sources)) {
        const caps = info.capabilities;
        if (caps.api && typeof caps.api === "object" && !Array.isArray(caps.api)) {
          map[name] = Object.keys(caps.api).filter(k => k !== "");
        }
      }
    }
    return map;
  }, [sources]);

  // all modes union for "all" platform
  const platformModes = useMemo(() => {
    const map: Record<string, string[]> = {};
    if (sources) {
      for (const [name, info] of Object.entries(sources)) {
        map[name] = Object.keys(info.capabilities);
      }
    }
    return map;
  }, [sources]);
  const allEngineModes = useMemo(() => Object.values(platformModes).flat().filter((m, i, a) => a.indexOf(m) === i), [platformModes]);

  // local state
  const searchQuery = "";
  const searchPlatform = "fanqie";
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [navigatingId, setNavigatingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const searchModeRef = useRef(SessionCache.getMode());
  const searchVariantRef = useRef<string | undefined>(SessionCache.getVariant());
  const navigatingRef = useRef(false);
  const [searchCachedQuery, setSearchCachedQuery] = useState("");
  const [resultTab, setResultTab] = useState<string>("all");
  const navigate = useNavigate();

  // search — using React Query
  const [searchParams, setSearchParams] = useState<{
    platform: string; query: string; mode?: string; variant?: string;
  } | null>(null);
  const { data: searchResults = [], isFetching: searching } = useSearch(searchParams);

  // 切回搜索 tab 时恢复上次搜索 UI 状态（不自动搜索）
  useEffect(() => {
    if (activeNav !== "search") return;
    const cached = SessionCache.getSearchParams();
    if (cached) {
      searchModeRef.current = SessionCache.getMode();
      searchVariantRef.current = SessionCache.getVariant();
      setSearchCachedQuery(cached.query);
    } else {
      const q = SessionCache.getSearchQuery();
      if (q) setSearchCachedQuery(q);
    }
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


  const handleOnlineSearch = useCallback(async (query: string, filters?: { platform?: string; mode?: string; variant?: string }) => {
    if (!query.trim()) { setSearchParams(null); SessionCache.clearSearch(); return; }
    const platform = filters?.platform || searchPlatform;
    const mode = filters?.mode ?? "browser";
    const variant = filters?.variant;
    searchModeRef.current = mode;
    searchVariantRef.current = variant 
    SessionCache.setMode(mode);
    SessionCache.setVariant(variant);
    SessionCache.saveSearch(query, platform, mode, variant);

    const isUrlOrId = query.startsWith("http://") || query.startsWith("https://") || /^\d+$/.test(query);
    if (isUrlOrId) {
      try {
        const meta = await fetchMetaMut.mutateAsync({ url: query, mode, variant });
        navigate(`/search/${meta.id}`, { state: { remoteUrl: query, searchMode: mode, searchVariant: variant, meta } });
      } catch (e: unknown) { toast((e as Error).message || "获取小说信息失败"); }
      return;
    }
    setSearchParams({ platform, query, mode, variant });
  }, [searchPlatform, navigate, toast, fetchMetaMut]);

  const handleGoToNovel = useCallback(async (result: SearchResult) => {
    if (navigatingRef.current) return;
    navigatingRef.current = true;
    setNavigatingId(result.url);
    const idMatch = result.url.match(/\/(page|book|info|shuku)\/(\d+)/);
    const maybeId = idMatch ? idMatch[2] : null;
    const local = maybeId ? novels.find(n => n.id === maybeId) : undefined;
    if (local) {
      navigate(`/search/${local.id}`, { state: { remoteUrl: result.url, searchMode: searchModeRef.current, searchVariant: searchVariantRef.current, meta: local } });
      return;
    }
    try {
      const meta = await fetchMetaMut.mutateAsync({ url: result.url, mode: searchModeRef.current, variant: searchVariantRef.current });
      navigate(`/search/${meta.id}`, { state: { remoteUrl: result.url, searchMode: searchModeRef.current, searchVariant: searchVariantRef.current, meta } });
    } catch (e: unknown) { toast((e as Error).message || "获取小说信息失败"); setNavigatingId(null); navigatingRef.current = false; }
  }, [navigate, novels, fetchMetaMut, toast]);

  const handleSettingsUpdate = useCallback((_path: string, _value: unknown) => {
    // 配置已在 SettingsView 内部通过 React Query 提交，此处仅重置保存标志
    setSaved(false);
  }, []);

  const handleSaveSettings = useCallback(async () => {
    if (!globalConfig) return;
    setSaving(true);
    try { await saveGlobalConfigMut.mutateAsync(globalConfig); setSaved(true); setTimeout(() => setSaved(false), 2500); }
    catch { console.warn("saveGlobalConfig failed"); }
    finally { setSaving(false); }
  }, [globalConfig, saveGlobalConfigMut]);

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
            if (filtered.length === 0) {
              return <div className="flex flex-col items-center justify-center py-20 text-slate-400"><p className="text-lg">{searchQuery ? "无匹配结果" : showFavoritesOnly ? "暂无收藏" : "书架空空"}</p></div>;
            }
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
      )}

      {activeNav === "downloads" && (
        <div className="mx-auto max-w-[720px] space-y-2 px-6 pt-12 pb-8 md:px-12">
          {tasks.length === 0 ? <p className="text-center text-sm text-slate-400 py-20">暂无下载任务</p>
            : tasks.map(task => {
              const pct = task.total > 0 ? Math.round((task.progress / task.total) * 100) : 0;
              const status = task.status as "downloading" | "paused" | "completed" | "failed" | "partial" | "cancelled";
              return (
                <DownloadTask key={task.task_id} title={task.title}
                  status={status} progress={pct} errorMessage={task.error ?? undefined}
                  currentTitle={task.current_title} chapters={task.chapters}
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
          <SearchBar onSearch={handleOnlineSearch} platforms={platforms} engineModes={allEngineModes} apiVariants={apiVariants} platformModes={platformModes} loading={searching} defaultQuery={searchCachedQuery} />
          {!searchParams && !searching && (
            <div className="flex flex-col items-center gap-3 py-16 px-6 text-xs text-slate-400">
              <div className="flex items-center gap-2"><span className="text-indigo-400 font-bold shrink-0">书籍ID</span><span className="bg-slate-100 rounded-md px-2 py-0.5 font-mono"># 1145141919810</span></div>
              <div className="flex items-center gap-2"><span className="text-indigo-400 font-bold shrink-0">网页端链接</span><span className="bg-slate-100 rounded-md px-2 py-0.5 font-mono truncate max-w-[320px]">https://fanqienovel.com/page/1145141919810</span></div>
              <div className="flex items-center gap-2"><span className="text-indigo-400 font-bold shrink-0">移动端分享链接</span><span className="bg-slate-100 rounded-md px-2 py-0.5 font-mono truncate max-w-[320px]">https://changdunovel.com/t/abc123/</span></div>
              <div className="flex items-center gap-2"><span className="text-indigo-400 font-bold shrink-0">直接搜索关键词</span><span className="bg-slate-100 rounded-md px-2 py-0.5">穿越：……</span></div>
            </div>
          )}
          {searchParams && searchResults.length === 0 && !searching && (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400">
              <p className="text-sm">未找到相关小说</p>
              <p className="mt-1 text-xs text-slate-300">试试换个关键词或平台</p>
            </div>
          )}
          {searchResults.length > 0 && (() => {
            const isAllPlatform = searchParams?.platform === "all";
            const PLATFORM_TABS = [
              { id: "all", label: "全部" },
              ...platforms.map(p => ({ id: p.id, label: p.label })),
            ];
            const grouped = isAllPlatform ? searchResults.filter(r => resultTab === "all" || r.platform === resultTab) : searchResults;
            const counts: Record<string, number> | null = isAllPlatform
              ? { all: searchResults.length, ...Object.fromEntries(platforms.map(p => [p.id, searchResults.filter(r => r.platform === p.id).length])) }
              : null;
            const activeTab = isAllPlatform ? resultTab : "all";
            return (
              <>
                {isAllPlatform && (
                  <div className="flex flex-wrap gap-1 self-start rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
                    {PLATFORM_TABS.map(t => (
                      <button key={t.id} onClick={() => setResultTab(t.id)}
                        className={cn(
                          "rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
                          activeTab === t.id
                            ? "bg-white text-slate-800 shadow-sm dark:bg-slate-700 dark:text-slate-200"
                            : "text-slate-500 hover:text-slate-700 dark:text-slate-400",
                        )}>
                        {t.label}{counts ? ` (${counts[t.id]})` : ""}
                      </button>
                    ))}
                  </div>
                )}
                <div className="grid grid-cols-1 gap-3">
                  {grouped.map((r, i) => (
                    <SearchResultCard key={i} title={r.title} author={r.author} description={r.description} rating={r.extra?.rating} loading={navigatingId === r.url} onClick={() => handleGoToNovel(r)} />
                  ))}
                </div>
              </>
            );
          })()}
        </div>
      )}

      {activeNav === "settings" && globalConfig && (
        <div className="px-6 pt-12 pb-8 md:px-12">
          <SettingsView globalConfig={globalConfig} saving={saving} saved={saved} onUpdate={handleSettingsUpdate} onSave={handleSaveSettings} />
        </div>
      )}
    </>
  );
}
