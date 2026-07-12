import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { AppShell } from "@/layout/AppShell";
import { ChevronDown } from "lucide-react";
import { BookCard, BookCardSkeleton } from "./BookCard";
import { SearchBar } from "./SearchBar";
import { SearchResultCard } from "./SearchResultCard";
import { DownloadTask } from "@/features/download/DownloadTask";
import { storageApi, coverToUrl, type NovelMeta } from "@/api/storage";
import { downloadApi, type SearchResult, type TaskInfo } from "@/api/download";
import { configApi, type AppConfig } from "@/api/config";
import { notify } from "@/lib/notify";
import { SettingsView } from "@/features/settings/SettingsPage";


type NavItem = "bookshelf" | "downloads" | "settings" | "search";

export default function BookshelfPage() {
  const { pathname } = useLocation();
  const activeNav: NavItem = useMemo(() => {
    if (pathname === "/downloads") return "downloads";
    if (pathname === "/settings") return "settings";
    if (pathname === "/search-tab") return "search";
    return "bookshelf";
  }, [pathname]);
  const [novels, setNovels] = useState<NovelMeta[]>([]);
  const [loadingNovels, setLoadingNovels] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [downloadTasks, setDownloadTasks] = useState<TaskInfo[]>([]);
  const [appName, setAppName] = useState("Novel下载器");
  const [searchPlatform, setSearchPlatform] = useState("fanqie");
  const [searchPlatforms, setSearchPlatforms] = useState<{ id: string; label: string }[]>([]);
  const [groups, setGroups] = useState<Record<string, Record<string, object>>>({});
  const [settings, setSettings] = useState<AppConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [navigatingId, setNavigatingId] = useState<string | null>(null);
  const navigatingRef = useRef(false);
  const searchModeRef = useRef("browser");
  const searchProviderRef = useRef<string | undefined>(undefined);
  const lastDownloadModeRef = useRef("browser");
  const lastDownloadProviderRef = useRef<string | undefined>(undefined);
  const prevTaskStatusRef = useRef<Record<string, string>>({});
  const navigate = useNavigate();

  useEffect(() => { storageApi.listNovels().then(setNovels).catch(e => console.error("书架加载失败:", e)).finally(() => setLoadingNovels(false)); }, []);
  useEffect(() => { configApi.get().then(c => { setSettings(c); setAppName(c.name); setGroups(c.groups); }).catch(e => console.error("配置加载失败:", e)); }, []);
  useEffect(() => { downloadApi.platforms().then(p => { setSearchPlatforms(p); if (p.length) setSearchPlatform(p[0].id); }).catch(e => console.error("平台列表加载失败:", e)); }, []);

  // --- 下载任务轮询（仅在下载管理 Tab 时）— 完成后自动刷新书架 ---
  useEffect(() => {
    if (activeNav !== "downloads") return;
    downloadApi.listTasks().then(setDownloadTasks).catch(() => {});
    const id = setInterval(() => {
      downloadApi.listTasks().then(tasks => {
        setDownloadTasks(tasks);
        const prev = prevTaskStatusRef.current;
        const hasJustFinished = tasks.some(
          t => (t.status === "completed" || t.status === "failed") && prev[t.task_id] === "downloading"
        );
        for (const t of tasks) prev[t.task_id] = t.status;
        if (hasJustFinished) {
          storageApi.refreshNovels().then(setNovels).catch(() => {});
        }
      }).catch(() => {});
    }, 1000);
    return () => clearInterval(id);
  }, [activeNav]);

  // --- refresh when tab becomes visible ---
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        storageApi.refreshNovels().then(setNovels).catch(() => {});
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

  const handleSearch = useCallback((query: string) => { setSearchQuery(query.trim()); }, []);

  const handleOnlineSearch = useCallback(async (query: string, filters?: { platform?: string; mode?: string; provider?: string }) => {
    if (!query.trim()) { setSearchResults([]); return; }
    setSearching(true);
    const platform = filters?.platform || searchPlatform;
    const mode = filters?.mode ?? "browser";
    const provider = filters?.provider;
    searchModeRef.current = mode;
    searchProviderRef.current = provider;
    try {
      const r = await downloadApi.search({ platform, query, mode, provider });
      // URL/ID 搜索 → 直接跳转详情
      const isUrlOrId = query.startsWith("http://") || query.startsWith("https://") || /^\d+$/.test(query);
      if (isUrlOrId && r.length === 1) {
        try {
          const meta = await downloadApi.fetchMeta(r[0].url, mode, provider);
          navigate(`/search/${meta.id}`, { state: { remoteUrl: r[0].url, searchMode: mode, searchProvider: provider, meta } });
        } catch { alert("获取小说信息失败"); }
        return;
      }
      if (isUrlOrId && r.length === 0) {
        alert("未找到该小说，请检查 URL 或 ID 是否正确");
        setSearchResults([]);
        return;
      }
      setSearchResults(r);
    } catch { setSearchResults([]); }
    finally { setSearching(false); }
  }, [searchPlatform, navigate]);

  const handleSettingsUpdate = useCallback((path: string, value: unknown) => {
    setSettings(prev => {
      if (!prev) return prev;
      const keys = path.split(".");
      if (keys.length === 1) {
        const updated = { ...prev, [keys[0]]: value };
        if (keys[0] === "name") setAppName(value as string);
        return updated;
      }
      const result = { ...prev } as Record<string, unknown>;
      let target: Record<string, unknown> = result;
      for (let i = 0; i < keys.length - 1; i++) {
        target[keys[i]] = { ...(target[keys[i]] as Record<string, unknown>) };
        target = target[keys[i]] as Record<string, unknown>;
      }
      target[keys[keys.length - 1]] = value;
      return result as unknown as AppConfig;
    });
    setSaved(false);
  }, []);

  const handleSaveSettings = useCallback(async () => {
    if (!settings) return;
    setSaving(true);
    try { await configApi.save(settings as unknown as Record<string, unknown>); setSaved(true); setTimeout(() => setSaved(false), 2500); }
    catch { /* ignore */ }
    finally { setSaving(false); }
  }, [settings]);

  // ── 分组 & 删除回调 ──
  const groupNames = useMemo(() => Object.keys(groups), [groups]);

  const saveGroups = useCallback(async (newGroups: Record<string, Record<string, object>>) => {
    if (!settings) return;
    const updated = { ...settings, groups: newGroups };
    setSettings(updated);
    setGroups(newGroups);
    try { await configApi.save(updated as unknown as Record<string, unknown>); }
    catch { /* ignore */ }
  }, [settings]);

  const handleDeleteNovel = useCallback((novelId: string) => {
    setNovels(prev => prev.filter(n => n.id !== novelId));
    // 从分组中移除
    const newGroups = { ...groups };
    for (const g of Object.keys(newGroups)) {
      if (novelId in newGroups[g]) {
        const { [novelId]: _, ...rest } = newGroups[g];
        if (Object.keys(rest).length === 0) delete newGroups[g];
        else newGroups[g] = rest;
        break;
      }
    }
    saveGroups(newGroups);
  }, [groups, saveGroups]);

  const handleMoveToGroup = useCallback((novelId: string, group: string) => {
    const newGroups = { ...groups };
    // 先从旧组移除
    for (const g of Object.keys(newGroups)) {
      if (novelId in newGroups[g]) {
        const { [novelId]: _, ...rest } = newGroups[g];
        if (Object.keys(rest).length === 0) delete newGroups[g];
        else newGroups[g] = rest;
        break;
      }
    }
    // 加入新组
    newGroups[group] = { ...newGroups[group], [novelId]: {} };
    saveGroups(newGroups);
  }, [groups, saveGroups]);

  const handleRemoveFromGroup = useCallback((novelId: string) => {
    const newGroups = { ...groups };
    for (const g of Object.keys(newGroups)) {
      if (novelId in newGroups[g]) {
        const { [novelId]: _, ...rest } = newGroups[g];
        if (Object.keys(rest).length === 0) delete newGroups[g];
        else newGroups[g] = rest;
        break;
      }
    }
    saveGroups(newGroups);
  }, [groups, saveGroups]);

  const handleNewGroup = useCallback((novelId: string, name: string) => {
    handleMoveToGroup(novelId, name);
  }, [handleMoveToGroup]);

  const handleDownloadAll = useCallback((novelId: string, mode: string, provider?: string) => {
    lastDownloadModeRef.current = mode;
    lastDownloadProviderRef.current = provider;
    const novel = novels.find(n => n.id === novelId);
    if (!novel) return;
    navigate(`/search/${novelId}`, { state: { remoteUrl: novel.url, searchMode: mode, searchProvider: provider } });
  }, [novels, navigate]);

  const handleGoToNovel = useCallback(async (result: SearchResult) => {
    if (navigatingRef.current) return;
    navigatingRef.current = true;
    setNavigatingId(result.url);
    // 从 URL 提取 possible ID → 检查本地是否存在
    const idMatch = result.url.match(/\/page\/(\d+)/);
    const maybeId = idMatch ? idMatch[1] : null;
    const local = maybeId ? novels.find(n => n.id === maybeId) : undefined;
    if (local) {
      navigate(`/search/${local.id}`, { state: { remoteUrl: result.url, searchMode: searchModeRef.current, searchProvider: searchProviderRef.current, meta: local } });
      return;
    }
    try {
      const meta = await downloadApi.fetchMeta(result.url, searchModeRef.current, searchProviderRef.current);
      navigate(`/search/${meta.id}`, { state: { remoteUrl: result.url, searchMode: searchModeRef.current, searchProvider: searchProviderRef.current, meta } });
    } catch { setNavigatingId(null); navigatingRef.current = false; }
  }, [navigate, novels]);

  const toPath: Record<string, string> = { bookshelf: "/bookshelf", search: "/search-tab", downloads: "/downloads", settings: "/settings" };

  return (
    <AppShell activeNav={activeNav} onNavigate={(item) => navigate(toPath[item])} searchQuery={searchQuery} onSearch={handleSearch} appName={appName}>
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
            // build novelId → group reverse map
            const groupMap = new Map<string, string>();
            for (const [group, ids] of Object.entries(groups)) {
              for (const id of Object.keys(ids)) groupMap.set(id, group);
            }
            // group novels
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
                      {items.map(novel => <BookCard key={novel.id} novelId={novel.id} title={novel.title} author={novel.author} onRead={() => navigate(`/novel/${novel.id}`)} groups={groupNames} currentGroup={tag === "未分类" ? undefined : tag} onDelete={handleDeleteNovel} onMoveToGroup={handleMoveToGroup} onRemoveFromGroup={handleRemoveFromGroup} onNewGroup={handleNewGroup} onDownloadAll={handleDownloadAll} serial={novel.serial} cover={coverToUrl(novel.cover)} defaultMode={lastDownloadModeRef.current} defaultProvider={lastDownloadProviderRef.current} />)}
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
          {downloadTasks.length === 0 ? <p className="text-center text-sm text-slate-400 py-20">暂无下载任务</p>
          : downloadTasks.map(task => {
            const pct = task.total > 0 ? Math.round((task.progress / task.total) * 100) : 0;
            const status = task.status as "downloading" | "paused" | "completed" | "failed";
            return (
              <DownloadTask key={task.task_id} title={task.title}
                status={status} progress={pct} errorMessage={task.error ?? undefined}
                currentTitle={task.current_title}
                onPause={() => downloadApi.pauseTask(task.task_id)}
                onResume={() => downloadApi.resumeTask(task.task_id)}
                onCancel={() => { downloadApi.deleteTask(task.task_id); setDownloadTasks(prev => prev.filter(t => t.task_id !== task.task_id)); }}
                onRetry={() => {}} />
            );
          })}
        </div>
      )}
      {activeNav === "search" && (
        <div className="mx-auto max-w-[1440px] space-y-6 px-6 pt-12 pb-8 md:px-12">
          <SearchBar onSearch={handleOnlineSearch} platforms={searchPlatforms} engineModes={["browser", "requests", "api"]} apiProviders={settings?.api_providers} loading={searching} />
          {searchResults.length > 0 && (
            <div className="grid grid-cols-1 gap-3">
              {searchResults.map((r, i) => (
                <SearchResultCard key={i} title={r.title} author={r.author} description={r.description} loading={navigatingId === r.url} onClick={() => handleGoToNovel(r)} />
              ))}
            </div>
          )}
        </div>
      )}
      {activeNav === "settings" && settings && <div className="px-6 pt-12 pb-8 md:px-12"><SettingsView cfg={settings} saving={saving} saved={saved} onUpdate={handleSettingsUpdate} onSave={handleSaveSettings} /></div>}
    </AppShell>
  );
}
