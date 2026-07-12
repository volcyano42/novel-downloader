import { useMemo } from "react";
import { Routes, Route, useLocation, Navigate } from "react-router-dom";
import { BookOpen, Download, Settings, User, Library, Search as SearchIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ToastProvider } from "@/components/Toast";
import BookshelfPage from "@/features/bookshelf/BookshelfPage";
import DetailPage from "@/features/detail/DetailPage";
import ReaderPage from "@/features/reader/ReaderPage";

type NavItem = "bookshelf" | "downloads" | "settings" | "search";

const DESKTOP_ITEMS: { id: NavItem; label: string; icon: typeof BookOpen }[] = [
  { id: "search", label: "搜索", icon: SearchIcon },
  { id: "bookshelf", label: "书架", icon: Library },
  { id: "downloads", label: "下载管理", icon: Download },
  { id: "settings", label: "设置", icon: Settings },
];

const TO_PATH: Record<string, string> = {
  bookshelf: "/bookshelf", search: "/search-tab",
  downloads: "/downloads", settings: "/settings",
};

export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AppShell />
      </ToastProvider>
    </ErrorBoundary>
  );
}

function AppShell() {
  const { pathname } = useLocation();

  const activeNav: NavItem = useMemo(() => {
    if (pathname === "/downloads") return "downloads";
    if (pathname === "/settings") return "settings";
    if (pathname === "/search-tab") return "search";
    return "bookshelf";
  }, [pathname]);

  const label = DESKTOP_ITEMS.find(i => i.id === activeNav)?.label ?? "Novel下载器";

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-64 shrink-0 border-r border-white/20 bg-white/60 backdrop-blur-xl">
        <div className="flex items-center gap-2 px-5 py-6">
          <BookOpen className="h-6 w-6 text-indigo-500" strokeWidth={1.5} />
          <span className="text-lg font-semibold text-slate-800">Novel下载器</span>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {DESKTOP_ITEMS.map(({ id, label: lbl, icon: Icon }) => (
            <a key={id} href={TO_PATH[id]}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium transition-all duration-200",
                activeNav === id
                  ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10"
                  : "text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800",
              )}>
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />{lbl}
            </a>
          ))}
        </nav>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        {/* Mobile header */}
        <header className="flex md:hidden items-center border-b border-white/20 bg-white/80 backdrop-blur-xl px-4 py-3 sticky top-0 z-30">
          <h1 className="text-base font-semibold text-slate-800">{label}</h1>
        </header>
        <div className="pb-20 md:pb-0">
          <Routes>
            <Route path="/" element={<Navigate to="/bookshelf" replace />} />
            <Route path="/bookshelf" element={<BookshelfPage />} />
            <Route path="/downloads" element={<BookshelfPage />} />
            <Route path="/settings" element={<BookshelfPage />} />
            <Route path="/search-tab" element={<BookshelfPage />} />
            <Route path="/novel/:novelId" element={<DetailPage />} />
            <Route path="/novel/:novelId/:chapterId" element={<ReaderPage />} />
            <Route path="/search/:novelId" element={<DetailPage />} />
          </Routes>
        </div>
      </main>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-30 flex md:hidden items-center justify-around border-t border-white/20 bg-white/90 backdrop-blur-xl px-2 py-2"
        style={{ paddingBottom: "calc(0.5rem + env(safe-area-inset-bottom, 0px))" }}>
        {DESKTOP_ITEMS.filter(i => i.id !== "settings").concat({ id: "settings" as NavItem, label: "我的", icon: User }).map(({ id, label: lbl, icon: Icon }) => (
          <a key={id} href={TO_PATH[id]}
            className={cn(
              "flex flex-col items-center gap-0.5 rounded-xl px-3 py-1.5 text-xs transition-colors",
              activeNav === id ? "text-indigo-500" : "text-slate-400",
            )}>
            <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />
            <span>{lbl}</span>
          </a>
        ))}
      </nav>
    </div>
  );
}
