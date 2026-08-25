import {Link, Navigate, Route, Routes, useLocation} from "react-router-dom";
import {useMemo, useState} from "react";
import {BookOpen, Download, Library, PanelLeftClose, PanelLeftOpen, Search as SearchIcon, Settings} from "lucide-react";
import {cn} from "@/lib/utils";
import {ErrorBoundary} from "@/components/ErrorBoundary";
import {ToastProvider} from "@/components/Toast";
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

  const [collapsed, setCollapsed] = useState(false);
  const label = DESKTOP_ITEMS.find(i => i.id === activeNav)?.label ?? "Novel下载器";

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900">
      {/* Desktop sidebar */}
      <aside className={cn(
        "hidden md:flex flex-col shrink-0 border-r border-white/20 bg-white/60 backdrop-blur-xl transition-all duration-300 relative",
        collapsed ? "w-14" : "w-64"
      )}>
        <button onClick={() => setCollapsed(!collapsed)}
          className="absolute top-3 right-3 rounded-lg p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors z-10">
          {collapsed ? <PanelLeftOpen className="h-4 w-4" strokeWidth={1.5} /> : <PanelLeftClose className="h-4 w-4" strokeWidth={1.5} />}
        </button>
        <div className={cn("flex items-center gap-2 px-5 py-6", collapsed && "justify-center px-0")}>
          {!collapsed && <><BookOpen className="h-6 w-6 text-indigo-500" strokeWidth={1.5} />
          <span className="text-lg font-semibold text-slate-800">Novel下载器</span></>}
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {DESKTOP_ITEMS.map(({ id, label: lbl, icon: Icon }) => (
            <Link key={id} to={TO_PATH[id]} title={collapsed ? lbl : undefined}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium transition-all duration-200",
                collapsed && "justify-center px-0",
                activeNav === id
                  ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10"
                  : "text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800",
              )}>
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />{!collapsed && lbl}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col min-h-0 min-w-0">
        {/* Mobile header */}
        <header className="flex md:hidden shrink-0 items-center border-b border-white/20 bg-white/80 backdrop-blur-xl px-4 py-3 z-30">
          <h1 className="text-base font-semibold text-slate-800">{label}</h1>
        </header>
        <div id="scroll-area" className="flex-1 overflow-y-auto overflow-x-hidden pb-20 md:pb-0 overscroll-contain" style={{ width: "100%", maxWidth: "100%" }}>
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
        {DESKTOP_ITEMS.map(({ id, label: lbl, icon: Icon }) => (
          <Link key={id} to={TO_PATH[id]}
            className={cn(
              "flex flex-col items-center gap-0.5 rounded-xl px-3 py-1.5 text-xs transition-colors",
              activeNav === id ? "text-indigo-500" : "text-slate-400",
            )}>
            <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />
            <span>{lbl}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
