import { useState, useMemo, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { BookCard, BookCardSkeleton } from "./BookCard";
import { SearchBar } from "./SearchBar";
import { SearchResultCard } from "./SearchResultCard";
import { DownloadTask } from "@/features/download/DownloadTask";
import { SettingsView } from "@/features/settings/SettingsPage";
import { useToast } from "@/components/Toast";
import { useNovels, useConfig, usePlatforms, useTasks, useSearch, useDeleteNovel, useSaveConfig, useFetchMeta } from "@/hooks/index";
import { coverToUrl, type NovelMeta, type SearchResult } from "@/api/endpoints";
import { pauseTask, resumeTask, deleteTask } from "@/api/endpoints";
import type { TaskInfo } from "@/api/endpoints";

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
  const { data: config } = useConfig();
  const { data: platforms = [] } = usePlatforms();
  const { data: tasks = [] } = useTasks(activeNav === "downloads");
  const toast = useToast();
  const deleteNovelMut = useDeleteNovel();
  const saveConfigMut = useSaveConfig();
  const fetchMetaMut = useFetchMeta();

  // local state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchPlatform, setSearchPlatform] = useState("fanqie");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [navigatingId, setNavigatingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const searchModeRef = useRef("browser");
  const searchProviderRef = useRef<string | undefined>(undefined);
  const lastDownloadModeRef = useRef("browser");
  const lastDownloadProviderRef = useRef<string | undefined>(undefined);
  const prevTaskStatusRef = useRef<Record<string, string>>({});
  const navigatingRef = useRef(false);
  const navigate = useNavigate();

  // search — using React Query
  const [searchParams, setSearchParams] = useState<{
    platform: string; query: string; mode?: string; provider?: string;
  } | null>(null);
  const { data: searchResults = [], isFetching: searching } = useSearch(searchParams);

  // tasks notification
  const tasksWithNotify = useMemo(() => {
    const prev = prevTaskStatusRef.current;
    const hasJustFinished = tasks.some(
      t => (t.status === "completed" || t.status === "failed") && prev[t.task_id] === "downloading",
    );
    for (const t of tasks) prev[t.task_id] = t.status;
    if (hasJustFinished) refetchNovels();
    return tasks;
  }, [tasks, refetchNovels]);

  const handleLocalSearch = useCallback((query: string) => setSearchQuery(query.trim()), []);

  const handleOnlineSearch = useCallback(async (query: string, filters?: { platform?: string; mode?: string; provider?: string }) => {
    if (!query.trim()) { setSearchParams(null); return; }
    const platform = filters?.platform || searchPlatform;
    const mode = filters?.mode ?? "browser";
    const provider = filters?.provider;
    searchModeRef.current = mode;
    searchProviderRef.current = provider;

    const isUrlOrId = query.startsWith("http://") || query.startsWith("https://") || /^\d+$/.test(query);
    if (isUrlOrId) {
      try {
        const meta = await fetchMetaMut.mutateAsync({ url: query, mode, provider });
        navigate(`/search/${meta.id}`, { state: { remoteUrl: query, searchMode: mode, searchProvider: provider, meta } });
      } catch (e: unknown) { toast((e as Error).message || "获取小说信息失败"); }
      return;
    }
    setSearchParams({ platform, query, mode, provider });
  }, [searchPlatform, navigate, toast, fetchMetaMut]);

  const handleGoToNovel = useCallback(async (result: SearchResult) => {
    if (navigatingRef.current) return;
    navigatingRef.current = true;
    setNavigatingId(result.url);
    const idMatch = result.url.match(/\/page\/(\d+)/);
    const maybeId = idMatch ? idMatch[1] : null;
    const local = maybeId ? novels.find(n => n.id === maybeId) : undefined;
    if (local) {
      navigate(`/search/${local.id}`, { state: { remoteUrl: result.url, searchMode: searchModeRef.current, searchProvider: searchProviderRef.current, meta: local } });
      return;
    }
    try {
      const meta = await fetchMetaMut.mutateAsync({ url: result.url, mode: searchModeRef.current, provider: searchProviderRef.current });
      navigate(`/search/${meta.id}`, { state: { remoteUrl: result.url, searchMode: searchModeRef.current, searchProvider: searchProviderRef.current, meta } });
    } catch { setNavigatingId(null); navigatingRef.current = false; }
  }, [navigate, novels, fetchMetaMut]);

  const handleSettingsUpdate = useCallback((path: string, value: unknown) => {
    // config is managed by React Query — we use setQueryData for optimistic update
    setSaved(false);
  }, []);

  const handleSaveSettings = useCallback(async () => {
    if (!config) return;
    setSaving(true);
    try { await saveConfigMut.mutateAsync(config as unknown as Record<string, unknown>); setSaved(true); setTimeout(() => setSaved(false), 2500); }
    catch { /* Toast handled by mutation */ }
    finally { setSaving(false); }
  }, [config, saveConfigMut]);

  // groups
  const groups = config?.groups ?? {};
  const groupNames = useMemo(() => Object.keys(groups), [groups]);

  const handleDeleteNovel = useCallback((novelId: string) => {
    deleteNovelMut.mutate(novelId);
  }, [deleteNovelMut]);

  const handleDownloadAll = useCallback((novelId: string, mode: string, provider?: string) => {
    lastDownloadModeRef.current = mode;
    lastDownloadProviderRef.current = provider;
    const novel = novels.find(n => n.id === novelId);
    if (!novel) return;
    navigate(`/search/${novelId}`, { state: { remoteUrl: novel.url, searchMode: mode, searchProvider: provider } });
  }, [novels, navigate]);

  const toPath: Record<string, string> = { bookshelf: "/bookshelf", search: "/search-tab", downloads: "/downloads", settings: "/settings" };

  return (
    <>
      {activeNav === "bookshelf" && (
        <div className="mx-auto max-w-[1440px] space-y-6 px-6 pt-12 pb-8 md:px-12">
          {loadingNovels ? (
            <div className="grid grid-cols-3 gap-5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7">{Array.from({ length: 6 }).map((_, i) => <BookCardSkeleton key={i} />)}</div>
          ) : (() => {
            const filtered = searchQuery
              ? novels.filter(n => n.title.includes(searchQuery) || n.author.includes(searchQuery))
              : novels;
            if (filtered.length === 0) {
              return <div className="flex flex-col items-center justify-center py-20 text-slate-400"><p className="text-lg">{searchQuery ? "无匹配结果" : "书架空空"}</p></div>;
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
                            onDownloadAll={handleDownloadAll}
                            serial={novel.serial}
                            cover={coverToUrl(novel.cover)}
                            defaultMode={lastDownloadModeRef.current}
                            defaultProvider={lastDownloadProviderRef.current}
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
          {tasksWithNotify.length === 0 ? <p className="text-center text-sm text-slate-400 py-20">暂无下载任务</p>
            : tasksWithNotify.map(task => {
              const pct = task.total > 0 ? Math.round((task.progress / task.total) * 100) : 0;
              const status = task.status as "downloading" | "paused" | "completed" | "failed";
              return (
                <DownloadTask key={task.task_id} title={task.title}
                  status={status} progress={pct} errorMessage={task.error ?? undefined}
                  currentTitle={task.current_title}
                  onPause={() => pauseTask(task.task_id)}
                  onResume={() => resumeTask(task.task_id)}
                  onCancel={() => deleteTask(task.task_id)}
                  onRetry={() => {}} />
              );
            })}
        </div>
      )}

      {activeNav === "search" && (
        <div className="mx-auto max-w-[1440px] space-y-6 px-6 pt-12 pb-8 md:px-12">
          <SearchBar onSearch={handleOnlineSearch} platforms={platforms} engineModes={["browser", "requests", "api"]} apiProviders={config?.api_providers} loading={searching} />
          {searchResults.length > 0 && (
            <div className="grid grid-cols-1 gap-3">
              {searchResults.map((r, i) => (
                <SearchResultCard key={i} title={r.title} author={r.author} description={r.description} loading={navigatingId === r.url} onClick={() => handleGoToNovel(r)} />
              ))}
            </div>
          )}
        </div>
      )}

      {activeNav === "settings" && config && (
        <div className="px-6 pt-12 pb-8 md:px-12">
          <SettingsView cfg={config} saving={saving} saved={saved} onUpdate={handleSettingsUpdate} onSave={handleSaveSettings} />
        </div>
      )}
    </>
  );
}
