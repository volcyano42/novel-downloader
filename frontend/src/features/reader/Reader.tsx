import {useCallback, useEffect, useRef, useState} from "react";
import {ChevronLeft, ChevronRight, ExternalLink, List, Moon, Sun, Type} from "lucide-react";
import {cn} from "@/lib/utils";
import {Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger} from "@/components/ui/sheet";

interface ImageData { raw_data: string | null; alt: string | null; insert: number | null; url: string | null; }
interface TocItem { id: string; title: string; url?: string; }
interface ReaderProps {
  title: string; content: string; images?: ImageData[]; chapters: TocItem[]; currentChapterId: string;
  author?: string; onNavigate: (chapterId: string) => void; onBack?: () => void; className?: string;
}

function buildImgTag(img: ImageData): string {
  let src = "";
  if (img.raw_data) {
    src = img.raw_data.startsWith("data:")
      ? img.raw_data
      : `data:image/jpeg;base64,${img.raw_data}`;
  } else if (img.url) {
    src = img.url;
  }
  const alt = img.alt ?? "";
  return `<img src="${src}" alt="${alt}" class="mx-auto my-4 max-w-full rounded-xl shadow-md" loading="lazy" />`;
}

function insertImages(content: string, images: ImageData[]): string {
  if (!images.length) return content;
  const positioned = images
    .filter((img): img is ImageData & { insert: number } => img.insert != null)
    .sort((a, b) => a.insert - b.insert);
  if (!positioned.length) return content;
  let result = content;
  for (let i = positioned.length - 1; i >= 0; i--) {
    const img = positioned[i];
    const pos = Math.max(0, Math.min(img.insert, result.length));
    result = result.slice(0, pos) + buildImgTag(img) + result.slice(pos);
  }
  return result;
}

export function Reader({ title, content, images = [], chapters, currentChapterId, author, onNavigate, onBack, className }: ReaderProps) {
  const [fontSize, setFontSize] = useState(18);
  const [isDark, setIsDark] = useState(() => typeof window !== "undefined" && document.documentElement.classList.contains("dark"));
  const navLock = useRef(false);

  // ---- 目录自动滚动 ----
  const [sheetOpen, setSheetOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);
  const hasAutoScrolled = useRef(false);
  const savedScrollTop = useRef(0);

  // 章节切换后重置滚动标记，下次打开目录重新定位
  useEffect(() => { hasAutoScrolled.current = false; }, [currentChapterId]);

  const onSheetChange = useCallback((open: boolean) => {
    if (!open && navRef.current) savedScrollTop.current = navRef.current.scrollTop;
    setSheetOpen(open);
  }, []);

  // Sheet 打开后：首次 scrollIntoView 到当前章节，之后恢复上次位置
  useEffect(() => {
    if (!sheetOpen) return;
    const raf = requestAnimationFrame(() => {
      const nav = navRef.current;
      if (!nav) return;
      if (!hasAutoScrolled.current) {
        const btn = nav.querySelector('[data-current="true"]') as HTMLElement | null;
        btn?.scrollIntoView({ behavior: "smooth", block: "center" });
        hasAutoScrolled.current = true;
      } else {
        nav.scrollTop = savedScrollTop.current;
      }
    });
    return () => cancelAnimationFrame(raf);
  }, [sheetOpen]);
  // --------------------------

  const toggleDark = useCallback(() => {
    const next = !isDark; setIsDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("reader-theme", next ? "dark" : "light");
  }, [isDark]);

  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if (navLock.current) return;
      const idx = chapters.findIndex(c => c.id === currentChapterId);
      if (e.key === "ArrowLeft" && idx > 0) { e.preventDefault(); navLock.current = true; onNavigate(chapters[idx - 1].id); }
      if (e.key === "ArrowRight" && idx < chapters.length - 1) { e.preventDefault(); navLock.current = true; onNavigate(chapters[idx + 1].id); }
    };
    const handleKeyUp = () => { navLock.current = false; };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => { window.removeEventListener("keydown", handleKeyDown); window.removeEventListener("keyup", handleKeyUp); };
  }, [chapters, currentChapterId, onNavigate]);

  const currentIdx = chapters.findIndex(c => c.id === currentChapterId);
  const hasPrev = currentIdx > 0, hasNext = currentIdx < chapters.length - 1;

  const htmlContent = insertImages(content, images)
    .split(/\n\n+/)
    .map(p => p.trim())
    .filter(Boolean)
    .map(p => `<p>${p}</p>`)
    .join("");

  return (
    <div className={cn("relative min-h-screen", className)}>
      <div className="pointer-events-none fixed inset-0 z-0 flex">
        <div className="flex-1 backdrop-blur-sm bg-slate-50/50 dark:bg-slate-950/50" />
        <div className="w-full max-w-[720px]" />
        <div className="flex-1 backdrop-blur-sm bg-slate-50/50 dark:bg-slate-950/50" />
      </div>

      <div className="sticky top-0 z-20 flex items-center justify-between gap-2 border-b border-white/20 bg-white/80 backdrop-blur-xl px-4 py-3">
        <div className="flex items-center gap-2 min-w-0">
          {onBack && <button onClick={onBack} className="rounded-lg p-1 text-slate-500 hover:bg-slate-100 shrink-0"><ChevronLeft className="h-[18px] w-[18px]" strokeWidth={1.5} /></button>}
          <span className="truncate text-sm font-medium text-slate-600">{title}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="flex items-center gap-1 rounded-lg bg-slate-100 dark:bg-slate-800 px-3 py-1">
            <Type className="h-3.5 w-3.5 text-slate-400" strokeWidth={1.5} />
            <input type="range" min={14} max={24} value={fontSize} onChange={e => setFontSize(Number(e.target.value))} className="h-1 w-16 appearance-none rounded-lg bg-slate-300 dark:bg-slate-600 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:rounded-lg [&::-webkit-slider-thumb]:bg-[#5e6ad2]/100" />
          </div>
          <button onClick={toggleDark} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            {isDark ? <Sun className="h-[18px] w-[18px]" strokeWidth={1.5} /> : <Moon className="h-[18px] w-[18px]" strokeWidth={1.5} />}
          </button>
          <Sheet open={sheetOpen} onOpenChange={onSheetChange}>
            <SheetTrigger asChild><button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"><List className="h-[18px] w-[18px]" strokeWidth={1.5} /></button></SheetTrigger>
            <SheetContent side="right" className="w-72">
              <SheetHeader><SheetTitle>目录</SheetTitle></SheetHeader>
              <nav ref={navRef} className="mt-4 flex flex-col gap-1 overflow-y-auto max-h-[80vh]">
                {chapters.map(ch => (
                  <button key={ch.id} onClick={() => onNavigate(ch.id)} data-current={ch.id === currentChapterId ? "true" : undefined} className={cn("rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-slate-100 dark:hover:bg-slate-800", ch.id === currentChapterId ? "bg-[#5e6ad2]/10 text-[#5e6ad2] dark:bg-[#5e6ad2]/100/10" : "text-slate-600 dark:text-slate-400")}>{ch.title}</button>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>

      <div className="relative z-10 mx-auto max-w-[720px] px-6 py-12">
        {title && (() => { const chUrl = chapters.find(c => c.id === currentChapterId)?.url; return (
          <h1 className="mb-8 flex items-start gap-2 font-serif font-bold text-slate-800 dark:text-slate-200" style={{ fontSize: `${fontSize + 6}px` }}>
            <span>{title}</span>
            {chUrl && <a href={chUrl} target="_blank" rel="noopener noreferrer" className="shrink-0 text-slate-300 hover:text-indigo-400 transition-colors" style={{ marginTop: `${Math.max(2, (fontSize + 6) * 0.15)}px` }}><ExternalLink className="h-[18px] w-[18px]" strokeWidth={1.5} /></a>}
          </h1>
        ); })()}
        <article
          className="prose prose-slate max-w-none font-serif dark:prose-invert [&_p]:indent-8"
          style={{ fontSize: `${fontSize}px`, lineHeight: "1.8" }}
          dangerouslySetInnerHTML={{ __html: htmlContent }}
        />
        {author && (
          <p className="mt-16 text-center text-xs text-slate-300 dark:text-slate-600">
            <span>仅供个人阅读使用 · 版权归 <span className="font-medium text-slate-400 dark:text-slate-500">{author}</span> 所有</span>
          </p>
        )}
        <div className="mt-8 flex items-center justify-between">
          <button onClick={() => hasPrev && onNavigate(chapters[currentIdx - 1].id)} disabled={!hasPrev} className="flex items-center gap-1 rounded-lg px-4 py-2 text-sm text-slate-500 transition-colors hover:text-[#5e6ad2] disabled:opacity-30"><ChevronLeft className="h-[18px] w-[18px]" strokeWidth={1.5} />上一章</button>
          <span className="text-xs text-slate-400">{currentIdx + 1} / {chapters.length}</span>
          <button onClick={() => hasNext && onNavigate(chapters[currentIdx + 1].id)} disabled={!hasNext} className="flex items-center gap-1 rounded-lg px-4 py-2 text-sm text-slate-500 transition-colors hover:text-[#5e6ad2] disabled:opacity-30">下一章<ChevronRight className="h-[18px] w-[18px]" strokeWidth={1.5} /></button>
        </div>
      </div>
    </div>
  );
}

export function ReaderSkeleton() {
  return (
    <div className="min-h-screen">
      <div className="sticky top-0 z-20 border-b border-white/20 bg-white/80 backdrop-blur-xl px-4 py-3">
        <div className="mx-auto max-w-[720px] flex items-center justify-between">
          <div className="h-4 w-32 animate-pulse rounded bg-slate-300/60" />
          <div className="flex gap-1"><div className="h-8 w-20 animate-pulse rounded-lg bg-slate-300/60" /><div className="h-8 w-8 animate-pulse rounded-lg bg-slate-300/60" /><div className="h-8 w-8 animate-pulse rounded-lg bg-slate-300/60" /></div>
        </div>
      </div>
      <div className="mx-auto max-w-[720px] px-6 py-12">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="mb-4"><div className="h-3 w-full animate-pulse rounded bg-slate-300/60 mb-2" /><div className="h-3 w-5/6 animate-pulse rounded bg-slate-300/60" /></div>)}</div>
    </div>
  );
}
