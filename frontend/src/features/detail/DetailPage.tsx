import { useState, useCallback, useEffect, useRef, useMemo, type WheelEvent } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { BookOpen, ChevronLeft, ExternalLink, Download, X, RefreshCw, Image, ChevronDown } from "lucide-react";
import { useNovelMeta, useRemoteChapters, useDownloadMutation, useGlobalConfig, compareChapters, useSources } from "@/hooks/index";
import { fetchChapterList, coverToUrl, streamChapters, type NovelMeta, type ChapterBrief } from "@/api/endpoints";
import { listChapters } from "@/api/endpoints";
import { DownloadDialog } from "@/features/download/DownloadDialog";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { useToast } from "@/components/Toast";
import { SessionCache } from "@/utils/sessionCache";
import { getCachedChapters, setCachedChapters } from "@/utils/chapterCache";

function platformFromUrl(url?: string): string {
  if (!url) return "fanqie";
  if (url.includes("fanqienovel.com") || url.includes("changdunovel.com")) return "fanqie";
  if (url.includes("qidian.com")) return "qidian";
  if (url.includes("qimao.com")) return "qimao";
  if (url.includes("92xs.info")) return "92xs";
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
  const st = location.state as { remoteUrl?: string; searchMode?: string; searchVariant?: string; meta?: NovelMeta } | null;
  const remoteUrl = st?.remoteUrl;
  const searchMode = st?.searchMode ?? "browser";
  const searchVariant = st?.searchVariant;
  const toast = useToast();

  const { data: localMeta, isLoading: metaLoading } = useNovelMeta(novelId);
  // 有 state 中的 remoteUrl，或本地 meta 404（小说未下载）→ 远程模式
  const isRemote = !!remoteUrl || (!metaLoading && !localMeta);
  // 远程模式缺 URL 时从 novelId 推断（纯数字 ID → 番茄）
  const effectiveRemoteUrl = remoteUrl || (isRemote && /^\d+$/.test(novelId!) ? `https://fanqienovel.com/page/${novelId}` : undefined);
  const plat = platformFromUrl(st?.meta?.url ?? effectiveRemoteUrl ?? localMeta?.url);
  const { data: sources } = useSources();
  const sourceCaps = sources?.[plat]?.capabilities ?? {};
  const platModes = Object.keys(sourceCaps);
  const platVariants = typeof sourceCaps.api === "object" && !Array.isArray(sourceCaps.api) ? Object.keys(sourceCaps.api).filter(k => k !== "") : [];
  const { data: remoteChapters } = useRemoteChapters(isRemote ? novelId : undefined, effectiveRemoteUrl, searchMode, searchVariant);
  const downloadMut = useDownloadMutation();
  const { data: globalConfig } = useGlobalConfig();

  const novel = st?.meta ?? localMeta ?? null;

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(isRemote);
  const [coverZoom, setCoverZoom] = useState(false);
  const [coverScale, setCoverScale] = useState(1);
  const [nearBottom, setNearBottom] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [checking, setChecking] = useState(false);
  const [checkMerged, setCheckMerged] = useState<MergedChapter[] | null>(null);

  // SSE 流式加载本地章节（本地展示 + 远程对比都需要）
  const [localChapters, setLocalChapters] = useState<ChapterBrief[]>([]);
  const [streaming, setStreaming] = useState(false);
  const cacheHydratedRef = useRef(false);
  const showLocal = !isRemote && !compareMode;

  // 远程模式下也加载本地章节用于对比，但仅在流完成后再预选
  useEffect(() => {
    if (!novelId) return;
    const needsLocal = showLocal || isRemote;
    if (!needsLocal) return;
    cacheHydratedRef.current = false;

    const cached = getCachedChapters(novelId);
    if (cached && cached.length) {
      setLocalChapters(cached);
      setStreaming(false);
      cacheHydratedRef.current = true;
    } else {
      setLocalChapters([]);
      setStreaming(true);
    }

    const ac = new AbortController();
    streamChapters(
      novelId,
      (ch: ChapterBrief) => {
        setLocalChapters(prev => {
          if (cacheHydratedRef.current) {
            const idx = prev.findIndex(c => c.id === ch.id);
            if (idx === -1) return [...prev, ch];
            const next = prev.slice();
            next[idx] = ch;
            return next;
          }
          return [...prev, ch];
        });
      },
      () => {
        if (!cacheHydratedRef.current) {
          setStreaming(false);
        }
      },
      ac.signal,
    );
    return () => ac.abort();
  }, [novelId, showLocal]);

  // 章节缓存：流完成后写回 sessionStorage
  useEffect(() => {
    if (!novelId || !showLocal) return;
    if (!streaming && localChapters.length) {
      setCachedChapters(novelId, localChapters);
    }
  }, [novelId, showLocal, streaming, localChapters]);

  const remoteMerged = isRemote && remoteChapters ? compareChapters(remoteChapters, localChapters) : [];
  const merged = compareMode && checkMerged ? checkMerged : remoteMerged;
  const chapters = isRemote ? [] : localChapters;
  const showCompare = isRemote || compareMode;
  const newCount = useMemo(() => {
    if (!compareMode || !checkMerged) return 0;
    return checkMerged.filter(mc => !mc.local || !mc.local.downloaded).length;
  }, [compareMode, checkMerged]);

  // 等待本地章节流加载完成后再预选，防止 SSE 未到时的错误全选
  useEffect(() => {
    if (remoteMerged.length > 0 && isRemote && !streaming) {
      const preSelected = new Set<string>();
      for (const mc of remoteMerged) {
        if (!mc.local || !mc.local.downloaded) preSelected.add(mc.remote.id);
      }
      setSelectedIds(preSelected);
      setLoading(false);
    }
  }, [remoteMerged, isRemote, streaming]);

  const allSelected = merged.length > 0 && selectedIds.size === merged.length;
  const localAllSelected = !showCompare && localChapters.length > 0 && selectedIds.size === localChapters.length;

  const toggleAll = useCallback(() => {
    if (allSelected) setSelectedIds(new Set());
    else setSelectedIds(new Set(merged.map(mc => mc.remote.id)));
  }, [allSelected, merged]);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const toggleAllLocal = useCallback(() => {
    if (localAllSelected) setSelectedIds(new Set());
    else setSelectedIds(new Set(localChapters.map(c => c.id)));
  }, [localAllSelected, localChapters]);

  const handleBack = () => navigate(-1);

  const handleCoverWheel = (e: WheelEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setCoverScale(prev => Math.min(5, Math.max(0.5, prev - e.deltaY * 0.005)));
  };

  useEffect(() => {
    const scrollArea = document.querySelector("#scroll-area") as HTMLElement | null;
    if (coverZoom) {
      document.body.style.overflow = "hidden";
      if (scrollArea) scrollArea.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
      if (scrollArea) scrollArea.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
      if (scrollArea) scrollArea.style.overflow = "";
    };
  }, [coverZoom]);

  const closeCover = () => { setCoverZoom(false); setCoverScale(1); };

  useEffect(() => {
    const el = document.querySelector("#scroll-area");
    if (!el) return;
    const onScroll = () => {
      setNearBottom(el.scrollTop + el.clientHeight >= el.scrollHeight - 200);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    onScroll(); // initial check
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  const scrollToEdge = () => {
    const el = document.querySelector("#scroll-area");
    if (!el) return;
    if (nearBottom) {
      setNearBottom(false);
      el.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      setNearBottom(true);
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  };

  const [dialogVariant, setDialogVariant] = useState<"download" | "check" | null>(null);
  const [savedMode, setSavedMode] = useState("");
  const [savedVariant, setSavedVariant] = useState("");

  const runCheckUpdate = useCallback(async (mode: string, variant?: string) => {
    setChecking(true);
    try {
      const remote = await fetchChapterList(novelId!, effectiveRemoteUrl ?? novel?.url ?? "", mode, variant);
      if (!remote.length) { toast("远端无章节数据"); return; }
      let localAll: ChapterBrief[];
      try {
        localAll = await listChapters(novelId!, { size: 20000 });
      } catch { toast("获取本地章节失败"); return; }
      const localMap = new Map(localAll.map(c => [c.id, c]));
      const m: MergedChapter[] = remote.map(r => ({ remote: r, local: localMap.get(r.id) ?? null }));
      const preSelected = new Set<string>();
      for (const mc of m) {
        if (!mc.local || !mc.local.downloaded) preSelected.add(mc.remote.id);
      }
      setCompareMode(true);
      setCheckMerged(m);
      setSelectedIds(preSelected);
    } catch (e: unknown) { toast((e as Error).message || "检查更新失败"); }
    finally { setChecking(false); }
  }, [novelId, effectiveRemoteUrl, novel?.url, toast]);

  const runDownloadLocal = useCallback((mode: string, variant?: string) => {
    if (!novelId || selectedIds.size === 0) return;
    const selected = localChapters
      .filter(c => selectedIds.has(c.id))
      .map(c => ({ id: c.id, url: c.url, novel_id: novelId, title: c.title, order: c.order, volume: c.volume }));
    downloadMut.mutate({
      novelId,
      chapters: selected,
      title: novel?.title ?? novelId,
      mode,
      variant,
      novelUrl: novel?.url,
      platform: platformFromUrl(novel?.url),
    });
    setSelectedIds(new Set());
    navigate("/downloads");
  }, [novelId, selectedIds, localChapters, novel?.title, novel?.url, navigate, downloadMut]);

  const runDownload = useCallback((mode: string, variant?: string) => {
    if (!novelId || selectedIds.size === 0) return;
    const selected = merged
      .filter(mc => selectedIds.has(mc.remote.id))
      .map(mc => ({ id: mc.remote.id, url: mc.remote.url, novel_id: novelId, title: mc.remote.title, order: mc.remote.order, volume: mc.remote.volume }));
    downloadMut.mutate({
      novelId,
      chapters: selected,
      title: novel?.title ?? novelId,
      mode,
      variant,
      novelUrl: novel?.url,
      platform: platformFromUrl(novel?.url),
    });
    setSelectedIds(new Set());
    navigate("/downloads");
  }, [novelId, selectedIds, merged, novel?.title, novel?.url, navigate, downloadMut]);

  const handleCheckUpdate = useCallback(() => {
    // 优先用本 session 选过的模式，兜底用 Settings 中的全局配置
    const mode = sessionStorage.getItem("nd:mode") ?? globalConfig?.mode ?? "browser";
    const variant = sessionStorage.getItem("nd:variant") ?? undefined;
    setSavedMode(mode);
    setSavedVariant(variant ?? "");
    setDialogVariant("check");
  }, [globalConfig?.mode]);

  const handleDownloadClick = useCallback(() => {
    setSavedMode(sessionStorage.getItem("nd:mode") ?? globalConfig?.mode ?? "browser");
    setSavedVariant(sessionStorage.getItem("nd:variant") ?? "");
    setDialogVariant("download");
  }, [globalConfig?.mode]);

  const handleDialogConfirm = useCallback((mode: string, variant?: string) => {
    setSavedMode(mode);
    setSavedVariant(variant ?? "");
    SessionCache.setMode(mode);
    SessionCache.setVariant(variant);
    const v = dialogVariant;
    setDialogVariant(null);
    if (v === "check") {
      runCheckUpdate(mode, variant);
    } else if (showCompare) {
      runDownload(mode, variant);
    } else {
      runDownloadLocal(mode, variant);
    }
  }, [dialogVariant, runCheckUpdate, runDownload, runDownloadLocal, showCompare]);

  // meta 加载完成后发现是远程小说，开启 loading 等远程章节
  useEffect(() => {
    if (!metaLoading && isRemote && !remoteUrl && !loading) {
      setLoading(true);
    }
  }, [metaLoading, isRemote, remoteUrl, loading]);

  if (!novel && !loading && !metaLoading) return <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900" />;

  const cover = coverToUrl(novel?.cover ?? null);
  return (
    <div className="bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900 animate-in fade-in duration-200">
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
            <div className="min-w-0 space-y-1 overflow-hidden">
              <a href={novel.url} target="_blank" rel="noopener noreferrer" className="group/title inline-flex items-center gap-1.5 text-xl font-semibold text-slate-800 hover:text-indigo-500 transition-colors">
                <span>{novel.title}</span>
                <ExternalLink className="h-4 w-4 opacity-0 group-hover/title:opacity-30 transition-opacity shrink-0" strokeWidth={1.5} />
              </a>
              <p className="text-sm text-slate-500">{novel.author}</p>
              <p className="text-xs text-slate-400 font-mono">{novel.id}</p>
              <p className="text-sm text-slate-500">{localChapters.length}/{novel.serial} 章{newCount > 0 && <span className="ml-1.5 inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-500 breathing-badge">+{newCount}</span>} · {novel.count ? `${novel.count.toLocaleString()} 字` : "字数未知"}</p>
              {novel.extra?.rating != null && <p className="text-xs text-slate-500 pt-0.5">{novel.extra.rating} 分</p>}
              {novel.tags && novel.tags.length > 0 && <div className="flex flex-wrap gap-1 pt-1">{novel.tags.map(t => <span key={t} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{t}</span>)}</div>}
            </div>
          </div>
          {novel.description && (
            <div className="relative mt-6">
              <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">{novel.description}</p>
            </div>
          )}
          <div className="mt-8 mb-3 flex flex-wrap items-center gap-3">
            <h3 className="text-base font-semibold text-slate-800">章节列表</h3>
            {streaming && <span className="text-xs text-amber-500">加载中...</span>}
            {showCompare && (
              <>
                <button onClick={toggleAll} className="text-xs text-slate-400 hover:text-indigo-500 transition-colors">{allSelected ? "全不选" : "全选"}</button>
                <span className="text-xs text-slate-500">已选择 <span className="font-medium text-indigo-500">{selectedIds.size}</span> 章</span>
                <div className="flex-1 min-w-0" />
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
                <button onClick={toggleAllLocal} className="text-xs text-slate-400 hover:text-indigo-500 transition-colors">{localAllSelected ? "全不选" : "全选"}</button>
                <span className="text-xs text-slate-500">已选择 <span className="font-medium text-indigo-500">{selectedIds.size}</span> 章</span>
                <div className="flex-1 min-w-0" />
                {selectedIds.size > 0 && (
                  <button onClick={handleDownloadClick}
                    className="rounded-full bg-indigo-500 text-white px-3 py-1 text-xs hover:bg-indigo-600 transition-colors flex items-center gap-1">
                    <Download className="h-3 w-3" strokeWidth={2} />
                    下载选中 ({selectedIds.size})
                  </button>
                )}
                <button onClick={handleCheckUpdate} disabled={checking} className="rounded-full bg-indigo-500 text-white px-3 py-1 text-xs hover:bg-indigo-600 transition-colors flex items-center gap-1 disabled:opacity-50">
                  <RefreshCw className={`h-3 w-3 ${checking ? "animate-spin" : ""}`} strokeWidth={2} />
                  {checking ? "检查中..." : "检查更新"}
                </button>
              </>
            )}
          </div>
          {loading ? (
            <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-10 animate-pulse rounded-xl bg-slate-200" />)}</div>
          ) : showCompare ? (
            <div className="max-h-[60vh] overflow-y-auto overscroll-contain space-y-1 border border-slate-200 rounded-xl px-2">
              {merged.map(mc => {
                const checked = selectedIds.has(mc.remote.id);
                const localOk = mc.local?.downloaded;
                const statusIcon = localOk ? "✓" : "✗";
                const statusColor = localOk ? "text-emerald-500" : "text-red-400";
                const statusTip = localOk ? "已下载" : "未下载";
                return (
                  <div key={mc.remote.id} className="flex items-center gap-2">
                    <label className="shrink-0 flex items-center cursor-pointer" onClick={(e) => { e.preventDefault(); toggleSelect(mc.remote.id); }}>
                      <input type="checkbox" checked={checked} readOnly className="sr-only peer" tabIndex={-1} />
                      <div className="h-4 w-4 rounded border-2 border-slate-300 peer-checked:border-indigo-500 peer-checked:bg-indigo-500 flex items-center justify-center transition-colors">
                        {checked && <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path d="M5 13l4 4L19 7" /></svg>}
                      </div>
                    </label>
                    <span className="inline-flex"><TooltipProvider><Tooltip><TooltipTrigger asChild><span className={`shrink-0 text-xs w-5 text-right cursor-default ${statusColor}`}>{statusIcon}</span></TooltipTrigger><TooltipContent side="top"><p className="text-xs">{statusTip}</p></TooltipContent></Tooltip></TooltipProvider></span>
                    <button onClick={() => mc.local && navigate(`/novel/${novelId}/${mc.remote.id}`)} disabled={!mc.local} className="group/ch flex-1 min-w-0 flex items-center rounded-xl px-4 py-2.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                      <span className="truncate text-slate-700 flex-1">{mc.remote.title}</span>
                      {(mc.remote.image_count ?? 0) > 0 && (
                        <span className="ml-1.5 shrink-0 inline-flex items-center gap-0.5 text-amber-500">
                          <Image className="h-3.5 w-3.5" strokeWidth={1.5} />
                          <span className="text-xs">{mc.remote.image_count}</span>
                        </span>
                      )}
                    </button>
                    <a href={mc.remote.url} target="_blank" rel="noopener noreferrer" className="shrink-0 p-2 text-slate-300 hover:text-indigo-400 transition-colors" onClick={e => e.stopPropagation()}>
                      <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.5} />
                    </a>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="max-h-[60vh] overflow-y-auto overscroll-contain space-y-1 border border-slate-200 rounded-xl px-2">
              {chapters.map(ch => {
                const checked = selectedIds.has(ch.id);
                return (
                <div key={ch.id} className="flex items-center gap-2">
                  <label className="shrink-0 flex items-center cursor-pointer" onClick={(e) => { e.preventDefault(); toggleSelect(ch.id); }}>
                    <input type="checkbox" checked={checked} readOnly className="sr-only peer" tabIndex={-1} />
                    <div className="h-4 w-4 rounded border-2 border-slate-300 peer-checked:border-indigo-500 peer-checked:bg-indigo-500 flex items-center justify-center transition-colors">
                      {checked && <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path d="M5 13l4 4L19 7" /></svg>}
                    </div>
                  </label>
                  <span className={`shrink-0 text-xs w-10 text-right tabular-nums ${ch.downloaded ? "text-emerald-500" : "text-slate-300"}`}>{ch.order}</span>
                  <button onClick={() => navigate(`/novel/${novelId}/${ch.id}`)} className="group/ch flex-1 min-w-0 flex items-center rounded-xl px-3 py-2.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                    <span className="truncate text-slate-700">{ch.title}</span>
                    {(ch.image_count ?? 0) > 0 && (
                      <span className="ml-1.5 shrink-0 inline-flex items-center gap-0.5 text-amber-500">
                        <Image className="h-3.5 w-3.5" strokeWidth={1.5} />
                        <span className="text-xs">{ch.image_count}</span>
                      </span>
                    )}
                  </button>
                  <a href={ch.url} target="_blank" rel="noopener noreferrer" className="shrink-0 p-2 text-slate-300 hover:text-indigo-400 transition-colors" onClick={e => e.stopPropagation()}>
                    <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.5} />
                  </a>
                </div>
                );
              })}
            </div>
          )}
          <p className="mt-12 text-center text-xs text-slate-300"><span>仅供个人阅读使用 · 版权归 <span className="font-medium text-slate-400">{novel?.author ?? "原作者"}</span> 所有</span></p>
        </div>
      )}

      {coverZoom && cover && (
        <div onClick={closeCover} onWheel={handleCoverWheel} className="fixed inset-0 z-50 flex items-center justify-center bg-black animate-in fade-in duration-200 p-8 overflow-hidden">
          <button onClick={closeCover} className="absolute top-4 right-4 rounded-full bg-white/20 p-2 text-white hover:bg-white/30 transition-colors z-10"><X className="h-5 w-5" strokeWidth={1.5} /></button>
          <img src={cover} alt={novel?.title} className="rounded-2xl object-contain shadow-2xl transition-transform duration-75" style={{ transform: `scale(${coverScale})`, maxHeight: "90vh", maxWidth: "90vw" }} onClick={e => e.stopPropagation()} />
        </div>
      )}

      {!loading && (
      <button onClick={scrollToEdge}
        className="fixed bottom-20 right-4 md:bottom-6 z-20 rounded-full bg-white/90 backdrop-blur shadow-lg border border-slate-200 p-2.5 text-slate-400 hover:text-indigo-500 hover:border-indigo-200 transition-all active:scale-95"
        aria-label={nearBottom ? "回到顶部" : "滚动到底部"}>
        <ChevronDown className={`h-5 w-5 transition-transform duration-300 ${nearBottom ? "rotate-180" : ""}`} strokeWidth={2} />
      </button>
      )}

      <DownloadDialog open={dialogVariant !== null} onClose={() => setDialogVariant(null)}
        dialogMode={dialogVariant ?? "download"} novelTitle={novel?.title ?? ""} chapterCount={selectedIds.size}
        initialMode={savedMode} initialVariant={savedVariant}
        availableModes={platModes} variants={platVariants}
        onStart={handleDialogConfirm} />
    </div>
  );
}
