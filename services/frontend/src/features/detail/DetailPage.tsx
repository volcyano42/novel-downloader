import { useState, useEffect, useCallback, type WheelEvent } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { BookOpen, ChevronLeft, ExternalLink, Download, X, RefreshCw } from "lucide-react";
import { storageApi, coverToUrl, type NovelMeta, type ChapterBrief } from "@/api/storage";
import { downloadApi } from "@/api/download";
import { DownloadDialog } from "@/features/download/DownloadDialog";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

function platformFromUrl(url?: string): string {
  if (!url) return "fanqie";
  if (url.includes("fanqienovel.com")) return "fanqie";
  if (url.includes("qidian.com")) return "qidian";
  if (url.includes("qimao.com")) return "qimao";
  return "fanqie";
}

interface MergedChapter {
  remote: ChapterBrief;
  local: ChapterBrief | null;
}

export default function DetailPage() {
  const { novelId } = useParams<{ novelId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const st = location.state as { remoteUrl?: string; searchMode?: string; searchProvider?: string; meta?: NovelMeta } | null;
  const remoteUrl = st?.remoteUrl;
  const searchMode = st?.searchMode ?? "browser";
  const searchProvider = st?.searchProvider;
  const isRemote = !!remoteUrl;
  const [novel, setNovel] = useState<NovelMeta | null>(null);
  const [chapters, setChapters] = useState<ChapterBrief[]>([]);
  const [merged, setMerged] = useState<MergedChapter[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [descExpanded, setDescExpanded] = useState(false);
  const [closing, setClosing] = useState(false);
  const [coverZoom, setCoverZoom] = useState(false);
  const [coverScale, setCoverScale] = useState(1);
  const [compareMode, setCompareMode] = useState(false);
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<"none" | "latest" | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 50;

  useEffect(() => {
    if (!novelId) return;
    setPage(1);
    setDescExpanded(false);
    setCompareMode(false);
    // 优先用传过来的 meta，否则从本地/远程加载
    if (st?.meta) {
      setNovel(st.meta);
    } else {
      const fetchLocalMeta = () => storageApi.getMeta(novelId);
      const fetchRemoteMeta = () => downloadApi.fetchMeta(remoteUrl!, searchMode, searchProvider);
      (isRemote ? fetchRemoteMeta().catch(fetchLocalMeta) : fetchLocalMeta())
        .then(setNovel).catch(() => {});
    }
  }, [novelId, remoteUrl, searchMode]);

  useEffect(() => {
    if (!novelId) return;
    setLoading(true);
    const ac = new AbortController();
    if (isRemote) {
      // fetch remote full list + local for comparison
      Promise.all([
        downloadApi.fetchChapterList(novelId, remoteUrl!, searchMode, searchProvider),
        storageApi.listChapters(novelId).catch(() => [] as ChapterBrief[]),
      ]).then(([remote, local]) => {
        if (ac.signal.aborted) return;
        const localMap = new Map(local.map((c: ChapterBrief) => [c.id, c]));
        const m: MergedChapter[] = remote.map((r: ChapterBrief) => ({ remote: r, local: localMap.get(r.id) ?? null }));
        setMerged(m);
        const preSelected = new Set<string>();
        for (const mc of m) {
          if (!mc.local || !mc.local.downloaded) preSelected.add(mc.remote.id);
        }
        setSelectedIds(preSelected);
      }).catch(() => {}).finally(() => { if (!ac.signal.aborted) setLoading(false); });
    } else {
      storageApi.listChapters(novelId, { page, size: pageSize })
        .then(paged => { if (!ac.signal.aborted) setChapters(paged); }).catch(() => {}).finally(() => { if (!ac.signal.aborted) setLoading(false); });
    }
    return () => ac.abort();
  }, [novelId, page, remoteUrl, searchMode]);

  const showCompare = isRemote || compareMode;
  const totalPages = Math.max(1, Math.ceil((novel?.serial ?? 0) / pageSize));
  const pagedChapters = chapters; // 本地模式已由服务端分页，远程模式使用 merged

  const allSelected = merged.length > 0 && selectedIds.size === merged.length;

  const toggleAll = useCallback(() => {
    if (allSelected) { setSelectedIds(new Set()); }
    else { setSelectedIds(new Set(merged.map(mc => mc.remote.id))); }
  }, [allSelected, merged]);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const handleBack = () => { setClosing(true); setTimeout(() => navigate("/"), 150); };

  const handleCoverWheel = (e: WheelEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setCoverScale(prev => Math.min(5, Math.max(0.5, prev - e.deltaY * 0.005)));
  };

  // lock body scroll when cover zoom is open
  useEffect(() => {
    if (coverZoom) { document.body.style.overflow = "hidden"; }
    else { document.body.style.overflow = ""; }
    return () => { document.body.style.overflow = ""; };
  }, [coverZoom]);

  const closeCover = () => { setCoverZoom(false); setCoverScale(1); };

  const [dialogVariant, setDialogVariant] = useState<"download" | "check" | null>(null);
  const [savedMode, setSavedMode] = useState("");
  const [savedProvider, setSavedProvider] = useState("");

  const runCheckUpdate = useCallback(async (mode: string, provider?: string) => {
    setChecking(true);
    setCheckResult(null);
    try {
      const remote = await downloadApi.fetchChapterList(novelId!, remoteUrl ?? novel?.url ?? "", mode, provider);
      const localAll = await storageApi.listChapters(novelId!, { size: 20000 }).catch(() => [] as ChapterBrief[]);
      const localMap = new Map(localAll.map((c: ChapterBrief) => [c.id, c]));
      const m: MergedChapter[] = remote.map((r: ChapterBrief) => ({ remote: r, local: localMap.get(r.id) ?? null }));
      const needsUpdate = m.some(mc => !mc.local || !mc.local.downloaded);
      if (needsUpdate) {
        setMerged(m);
        const preSelected = new Set<string>();
        for (const mc of m) {
          if (!mc.local || !mc.local.downloaded) preSelected.add(mc.remote.id);
        }
        setSelectedIds(preSelected);
        setCompareMode(true);
      } else {
        setCheckResult("latest");
        setTimeout(() => setCheckResult(null), 2000);
      }
    } catch { /* ignore */ }
    finally { setChecking(false); }
  }, [novelId, remoteUrl, novel?.url]);

  const runDownload = useCallback((mode: string, provider?: string) => {
    if (!novelId || selectedIds.size === 0) return;
    const selected = merged
      .filter(mc => selectedIds.has(mc.remote.id))
      .map(mc => ({ id: mc.remote.id, url: mc.remote.url, novel_id: novelId, title: mc.remote.title, order: mc.remote.order, volume: mc.remote.volume }));
    downloadApi.downloadChapters(novelId, selected, novel?.title ?? novelId, mode, provider, novel?.url, platformFromUrl(novel?.url));
    setSelectedIds(new Set());
    navigate("/downloads");
  }, [novelId, selectedIds, merged, novel?.title, novel?.url, navigate]);

  const handleCheckUpdate = useCallback(() => {
    setDialogVariant("check");
  }, []);

  const handleDownloadClick = useCallback(() => {
    if (savedMode) {
      runDownload(savedMode, savedProvider || undefined);
    } else {
      setDialogVariant("download");
    }
  }, [savedMode, savedProvider, runDownload]);

  const handleDialogConfirm = useCallback((mode: string, provider?: string) => {
    setSavedMode(mode);
    setSavedProvider(provider ?? "");
    const v = dialogVariant;
    setDialogVariant(null);
    if (v === "check") {
      runCheckUpdate(mode, provider);
    } else {
      runDownload(mode, provider);
    }
  }, [dialogVariant, runCheckUpdate, runDownload]);

  if (!novel && !loading) return <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900" />;

  const cover = coverToUrl(novel?.cover ?? null);
  return (
    <div className={`min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900 animate-in fade-in duration-200 ${closing ? "animate-out fade-out duration-150" : ""}`}>
      <div className="sticky top-0 z-20 flex items-center gap-2 border-b border-white/20 bg-white/80 backdrop-blur-xl px-4 py-3">
        <button onClick={handleBack} className="rounded-full p-1 text-slate-500 hover:bg-slate-100"><ChevronLeft className="h-[18px] w-[18px]" strokeWidth={1.5} /></button>
        <span className="truncate text-sm font-medium text-slate-600">书籍详情</span>
      </div>
      {novel && (
        <div className="mx-auto max-w-[720px] px-4 py-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
          <div className="flex gap-6 relative">
            <div onClick={() => cover && setCoverZoom(true)} className={`w-28 shrink-0 aspect-[4/5] rounded-2xl bg-slate-100 overflow-hidden animate-in zoom-in-95 duration-300 ${cover ? "cursor-zoom-in" : ""}`}>
              {cover ? <img src={cover} alt={novel.title} className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center"><BookOpen className="h-8 w-8 text-slate-300" strokeWidth={1.5} /></div>}
            </div>
            <div className="min-w-0 space-y-1">
              <a href={novel.url} target="_blank" rel="noopener noreferrer" className="group/title inline-flex items-center gap-1.5 text-xl font-semibold text-slate-800 hover:text-indigo-500 transition-colors">
                <span>{novel.title}</span>
                <ExternalLink className="h-4 w-4 opacity-0 group-hover/title:opacity-30 transition-opacity shrink-0" strokeWidth={1.5} />
              </a>
              <p className="text-sm text-slate-500">{novel.author}</p>
              <p className="text-xs text-slate-400 font-mono">{novel.id}</p>
              <p className="text-sm text-slate-500">共 {novel.serial} 章 · {novel.count ? `${novel.count.toLocaleString()} 字` : "字数未知"}</p>
              {novel.tags && novel.tags.length > 0 && <div className="flex flex-wrap gap-1 pt-1">{novel.tags.map(t => <span key={t} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{t}</span>)}</div>}
            </div>
          </div>
          {novel.description && (
            <div className="relative mt-6">
              <div className={`overflow-hidden transition-all duration-300 ease-in-out ${descExpanded ? "max-h-[2000px]" : "max-h-[5.5rem]"}`}>
                <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">
                  {novel.description}
                </p>
              </div>
              {!descExpanded && novel.description.length > 200 && (
                <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-slate-50 to-transparent dark:from-slate-950 pointer-events-none" />
              )}
              {novel.description.length > 200 && (
                <button onClick={() => setDescExpanded(!descExpanded)} className="mt-1 text-xs text-indigo-500 hover:text-indigo-600">
                  {descExpanded ? "收起" : "展开全部"}
                </button>
              )}
            </div>
          )}
          <div className="mt-8 mb-3 flex items-center gap-3">
            <h3 className="text-base font-semibold text-slate-800">章节列表</h3>
            {showCompare && (
              <>
                <button onClick={toggleAll} className="text-xs text-slate-400 hover:text-indigo-500 transition-colors">{allSelected ? "全不选" : "全选"}</button>
                <span className="text-xs text-slate-500">已选择 <span className="font-medium text-indigo-500">{selectedIds.size}</span> 章</span>
                <div className="flex-1" />
                {selectedIds.size > 0 && (
                  <button onClick={handleDownloadClick}
                    className="rounded-full bg-indigo-500 text-white px-3 py-1 text-xs hover:bg-indigo-600 transition-colors flex items-center gap-1">
                    <Download className="h-3 w-3" strokeWidth={2} />
                    下载选中 ({selectedIds.size})
                  </button>
                )}
              </>
            )}
            {!isRemote && !compareMode && (
              <>
                <div className="flex-1" />
                <button onClick={handleCheckUpdate} disabled={checking} className="rounded-full bg-indigo-500 text-white px-3 py-1 text-xs hover:bg-indigo-600 transition-colors flex items-center gap-1 disabled:opacity-50">
                  <RefreshCw className={`h-3 w-3 ${checking ? "animate-spin" : ""}`} strokeWidth={2} />
                  {checking ? "检查中..." : checkResult === "latest" ? "已是最新 ✓" : "检查更新"}
                </button>
              </>
            )}
          </div>
          {loading ? (
            <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-10 animate-pulse rounded-xl bg-slate-200" />)}</div>
          ) : showCompare ? (
            <div className="space-y-1">
              {merged.map(mc => {
                const checked = selectedIds.has(mc.remote.id);
                const localOk = mc.local?.downloaded;
                const statusIcon = localOk ? "✓" : "✗";
                const statusColor = localOk ? "text-emerald-500" : "text-red-400";
                const statusTip = localOk ? "已下载" : "未下载";
                return (
                  <div key={mc.remote.id} className="flex items-center gap-2">
                    <label className="shrink-0 flex items-center cursor-pointer">
                      <input type="checkbox" checked={checked} onChange={() => toggleSelect(mc.remote.id)} className="sr-only peer" />
                      <div className="h-4 w-4 rounded border-2 border-slate-300 peer-checked:border-indigo-500 peer-checked:bg-indigo-500 flex items-center justify-center transition-colors">
                        {checked && <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path d="M5 13l4 4L19 7" /></svg>}
                      </div>
                    </label>
                    <TooltipProvider><Tooltip><TooltipTrigger asChild><span className={`shrink-0 text-xs w-5 text-right cursor-default ${statusColor}`}>{statusIcon}</span></TooltipTrigger><TooltipContent side="top"><p className="text-xs">{statusTip}</p></TooltipContent></Tooltip></TooltipProvider>
                    <button onClick={() => mc.local && navigate(`/novel/${novelId}/${mc.remote.id}`)} disabled={!mc.local} className="group/ch flex-1 flex items-center rounded-xl px-4 py-2.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                      <span className="truncate text-slate-700 flex-1">{mc.remote.title}</span>
                    </button>
                    <a href={mc.remote.url} target="_blank" rel="noopener noreferrer" className="shrink-0 p-2 text-slate-300 hover:text-indigo-400 transition-colors" onClick={e => e.stopPropagation()}>
                      <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.5} />
                    </a>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="space-y-1">
              {pagedChapters.map(ch => (
                <div key={ch.id} className="flex items-center gap-2">
                  <span className={`shrink-0 text-xs w-10 text-right ${ch.downloaded ? "text-emerald-500" : "text-red-400"}`}>{ch.downloaded ? "✓" : "✗"}</span>
                  <button onClick={() => navigate(`/novel/${novelId}/${ch.id}`)} className="group/ch flex-1 flex items-center rounded-xl px-4 py-2.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                    <span className="truncate text-slate-700 flex-1">{ch.title}</span>
                  </button>
                  <a href={ch.url} target="_blank" rel="noopener noreferrer" className="shrink-0 p-2 text-slate-300 hover:text-indigo-400 transition-colors" onClick={e => e.stopPropagation()}>
                    <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.5} />
                  </a>
                </div>
              ))}
            </div>
          )}
          {!showCompare && totalPages > 1 && (() => {
            const pages: number[] = [];
            const start = Math.max(1, page - 2);
            const end = Math.min(totalPages, page + 2);
            for (let i = start; i <= end; i++) pages.push(i);
            return (
              <div className="mt-6 flex items-center justify-center gap-1">
                <button onClick={() => setPage(1)} disabled={page <= 1} className="rounded-lg px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-100 disabled:opacity-20 transition-colors">1</button>
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} className="rounded-lg px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-100 disabled:opacity-20 transition-colors">‹</button>
                {start > 1 && <span className="px-1 text-xs text-slate-300">…</span>}
                {pages.map(p => (
                  <button key={p} onClick={() => setPage(p)} className={`rounded-lg px-2.5 py-1.5 text-xs transition-colors ${p === page ? "bg-indigo-500 text-white" : "text-slate-500 hover:bg-slate-100"}`}>{p}</button>
                ))}
                {end < totalPages && <span className="px-1 text-xs text-slate-300">…</span>}
                <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="rounded-lg px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-100 disabled:opacity-20 transition-colors">›</button>
                <button onClick={() => setPage(totalPages)} disabled={page >= totalPages} className="rounded-lg px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-100 disabled:opacity-20 transition-colors">{totalPages}</button>
              </div>
            );
          })()}
          <p className="mt-12 text-center text-xs text-slate-300"><span>仅供个人阅读使用 · 版权归 <span className="font-medium text-slate-400">{novel?.author ?? "原作者"}</span> 所有</span></p>
        </div>
      )}

      {/* cover zoom modal */}
      {coverZoom && cover && (
        <div onClick={closeCover} onWheel={handleCoverWheel} className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm animate-in fade-in duration-200 p-8 overflow-hidden">
          <button onClick={closeCover} className="absolute top-4 right-4 rounded-full bg-white/20 p-2 text-white hover:bg-white/30 transition-colors z-10"><X className="h-5 w-5" strokeWidth={1.5} /></button>
          <img src={cover} alt={novel?.title} className="rounded-2xl object-contain shadow-2xl transition-transform duration-75" style={{ transform: `scale(${coverScale})`, maxHeight: "90vh", maxWidth: "90vw" }} onClick={e => e.stopPropagation()} />
        </div>
      )}

      {/* download / check-update dialog */}
      <DownloadDialog open={dialogVariant !== null} onClose={() => setDialogVariant(null)}
        variant={dialogVariant ?? "download"} novelTitle={novel?.title ?? ""} chapterCount={selectedIds.size}
        initialMode={savedMode} initialProvider={savedProvider}
        onStart={handleDialogConfirm} />
    </div>
  );
}

