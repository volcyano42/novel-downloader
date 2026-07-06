import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { AppShell } from "@/layout/AppShell";
import { ChevronDown } from "lucide-react";
import { BookCard, BookCardSkeleton } from "./BookCard";
import { SearchBar } from "./SearchBar";
import { SearchResultCard } from "./SearchResultCard";
import { DownloadTask } from "@/features/download/DownloadTask";
import { storageApi, coverToUrl, type NovelMeta } from "@/api/storage";
import { downloadApi, type SearchResult } from "@/api/download";
import { configApi, type AppConfig } from "@/api/config";
import { SettingsView } from "@/features/settings/SettingsPage";
import { useCrossTab, SyncEvent } from "@/lib/sync";

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
  const [downloadTasks, setDownloadTasks] = useState<{ id: string; title: string; status: "downloading" | "completed" | "failed"; progress: number; error?: string }[]>([]);
  const [appName, setAppName] = useState("Novel下载器");
  const [searchPlatform, setSearchPlatform] = useState("fanqie");
  const [searchPlatforms, setSearchPlatforms] = useState<{ id: string; label: string }[]>([]);
  const [groups, setGroups] = useState<Record<string, Record<string, object>>>({});
  const [settings, setSettings] = useState<AppConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [navigatingId, setNavigatingId] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => { storageApi.listNovels().then(setNovels).catch(() => {}).finally(() => setLoadingNovels(false)); }, []);
  useEffect(() => { configApi.get().then(c => { setSettings(c); setAppName(c.name); setGroups(c.groups); }).catch(() => {}); }, []);
  useEffect(() => { downloadApi.platforms().then(p => { setSearchPlatforms(p); if (p.length) setSearchPlatform(p[0].id); }).catch(() => {}); }, []);

  // --- cross-tab sync ---
  const broadcast = useCrossTab((type, payload) => {
    switch (type) {
      case SyncEvent.DOWNLOAD_STARTED: {
        const p = payload as { id: string; title: string };
        setDownloadTasks(prev => {
          if (prev.some(t => t.id === p.id)) return prev;
          return [...prev, { id: p.id, title: p.title, status: "downloading" as const, progress: 0 }];
        });
        break;
      }
      case SyncEvent.DOWNLOAD_COMPLETED: {
        const p = payload as { id: string };
        setDownloadTasks(prev => prev.map(t => t.id === p.id ? { ...t, status: "completed" as const, progress: 100 } : t));
        break;
      }
      case SyncEvent.DOWNLOAD_FAILED: {
        const p = payload as { id: string; error: string };
        setDownloadTasks(prev => prev.map(t => t.id === p.id ? { ...t, status: "failed" as const, error: p.error } : t));
        break;
      }
      case SyncEvent.NOVELS_CHANGED:
        storageApi.listNovels().then(setNovels).catch(() => {});
        break;
    }
  });

  // --- refresh when tab becomes visible ---
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        storageApi.listNovels().then(setNovels).catch(() => {});
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

  const handleSearch = useCallback((query: string) => { setSearchQuery(query.trim()); }, []);

  const handleOnlineSearch = useCallback(async (query: string, filters?: { platform?: string }) => {
    if (!query.trim()) { setSearchResults([]); return; }
    const platform = filters?.platform || searchPlatform;
    try { const r = await downloadApi.search({ platform, query }); setSearchResults(r); } catch { setSearchResults([]); }
  }, [searchPlatform]);

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
    try { await configApi.save(settings); setSaved(true); setTimeout(() => setSaved(false), 2500); }
    catch { /* ignore */ }
    finally { setSaving(false); }
  }, [settings]);

  const handleGoToNovel = useCallback(async (result: SearchResult) => {
    setNavigatingId(result.url);
    try {
      const meta = await downloadApi.fetchMeta(result.url);
      navigate(`/search/${meta.id}`, { state: { remoteUrl: result.url } });
    } catch { setNavigatingId(null); }
  }, [navigate]);

  const toPath: Record<string, string> = { bookshelf: "/bookshelf", search: "/search-tab", downloads: "/downloads", settings: "/settings" };

  return (
    <AppShell activeNav={activeNav} onNavigate={(item) => navigate(toPath[item])} searchQuery={searchQuery} onSearch={handleSearch} appName={appName}>
      {activeNav === "bookshelf" && (
        <div className="mx-auto max-w-[1440px] space-y-6 px-4 py-6 md:px-8">
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
                      {items.map(novel => <BookCard key={novel.id} novelId={novel.id} title={novel.title} author={novel.author} cover={coverToUrl(novel.cover) ?? undefined} onRead={() => navigate(`/novel/${novel.id}`)} />)}
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
        <div className="space-y-2 px-4 py-6 md:px-8">
          {downloadTasks.length === 0 ? <p className="text-center text-sm text-slate-400 py-20">暂无下载任务</p>
          : downloadTasks.map(task => <DownloadTask key={task.id} title={task.title} status={task.status} progress={task.progress} errorMessage={task.error} onCancel={() => setDownloadTasks(prev => prev.filter(t => t.id !== task.id))} onRetry={() => {}} />)}
        </div>
      )}
      {activeNav === "search" && (
        <div className="mx-auto max-w-[1440px] space-y-6 px-4 py-6 md:px-8">
          <SearchBar onSearch={handleOnlineSearch} platforms={searchPlatforms} />
          {searchResults.length > 0 && (
            <div className="grid grid-cols-1 gap-3">
              {searchResults.map((r, i) => (
                <SearchResultCard key={i} title={r.title} author={r.author} description={r.description} loading={navigatingId === r.url} onClick={() => handleGoToNovel(r)} />
              ))}
            </div>
          )}
        </div>
      )}
      {activeNav === "settings" && settings && <div className="px-4 py-6 md:px-8"><SettingsView cfg={settings} saving={saving} saved={saved} onUpdate={handleSettingsUpdate} onSave={handleSaveSettings} /></div>}
    </AppShell>
  );
}
