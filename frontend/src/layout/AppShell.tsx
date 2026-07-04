import { useState, type ReactNode, type ChangeEvent } from "react";
import { BookOpen, Download, Settings, User, Menu, Library, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

type NavItem = "bookshelf" | "downloads" | "settings" | "search";

interface AppShellProps {
  children: ReactNode; activeNav: NavItem; onNavigate: (item: NavItem) => void;
  searchQuery?: string; onSearch?: (query: string) => void;
  appName?: string; userName?: string; userAvatar?: string; className?: string;
}

const desktopItems: { id: NavItem; label: string; icon: typeof BookOpen }[] = [
  { id: "search", label: "搜索", icon: Search },
  { id: "bookshelf", label: "书架", icon: Library },
  { id: "downloads", label: "下载管理", icon: Download },
  { id: "settings", label: "设置", icon: Settings },
];
const mobileItems = [...desktopItems, { id: "settings" as NavItem, label: "我的", icon: User }];

export function AppShell({ children, activeNav, onNavigate, searchQuery = "", onSearch, appName = "Novel下载器", userName = "读者", userAvatar, className }: AppShellProps) {
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <div className={cn("flex h-screen overflow-hidden bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900", className)}>
      <aside className="hidden md:flex flex-col w-64 shrink-0 border-r border-white/20 bg-white/60 backdrop-blur-xl">
        <div className="flex items-center justify-between px-5 py-6">
          <div className="flex items-center gap-2"><BookOpen className="h-6 w-6 text-indigo-500" strokeWidth={1.5} /><span className="text-lg font-semibold text-slate-800">{appName}</span></div>
          {onSearch && (
            <button onClick={() => { setSearchOpen(!searchOpen); if (searchOpen) onSearch(""); }} className={cn("rounded-full p-1.5 transition-colors", searchOpen ? "bg-indigo-50 text-indigo-500" : "text-slate-400 hover:text-slate-600 hover:bg-slate-100")}>
              <Search className="h-[18px] w-[18px]" strokeWidth={1.5} />
            </button>
          )}
        </div>
        {onSearch && searchOpen && (
          <div className="px-3 pb-3 animate-in slide-in-from-top-2 fade-in duration-150">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" strokeWidth={1.5} />
              <input autoFocus type="text" value={searchQuery} onChange={(e: ChangeEvent<HTMLInputElement>) => onSearch?.(e.target.value)} placeholder="搜索书名、作者..." className="w-full rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm py-2 pl-8 pr-8 text-xs text-slate-700 placeholder:text-slate-400 outline-none transition-shadow focus:ring-2 focus:ring-indigo-500/20" />
              {searchQuery && <button onClick={() => onSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"><X className="h-3 w-3" strokeWidth={1.5} /></button>}
            </div>
          </div>
        )}
        <nav className="flex-1 space-y-1 px-3">
          {desktopItems.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => onNavigate(id)} className={cn("flex w-full items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium transition-all duration-200", activeNav === id ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10" : "text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800")}><Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />{label}</button>
          ))}
        </nav>
        <div className="border-t border-white/20 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-indigo-600 dark:bg-indigo-500/20 overflow-hidden">
              {userAvatar ? <img src={userAvatar} alt={userName} className="h-full w-full object-cover" /> : <User className="h-[18px] w-[18px]" strokeWidth={1.5} />}
            </div>
            <span className="truncate text-sm font-medium text-slate-700">{userName}</span>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <header className="flex md:hidden items-center justify-between border-b border-white/20 bg-white/80 backdrop-blur-xl px-4 py-3 sticky top-0 z-30">
          <Sheet open={mobileDrawerOpen} onOpenChange={setMobileDrawerOpen}>
            <SheetTrigger asChild><button className="rounded-full p-2 text-slate-500 hover:bg-slate-100"><Menu className="h-[18px] w-[18px]" strokeWidth={1.5} /></button></SheetTrigger>
            <SheetContent side="left" className="w-64">
              <div className="flex items-center gap-2 mb-6"><BookOpen className="h-5 w-5 text-indigo-500" strokeWidth={1.5} /><span className="text-lg font-semibold text-slate-800">{appName}</span></div>
              <nav className="space-y-1">
                {desktopItems.map(({ id, label, icon: Icon }) => (
                  <button key={id} onClick={() => { onNavigate(id); setMobileDrawerOpen(false); }} className={cn("flex w-full items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium transition-all", activeNav === id ? "bg-indigo-50 text-indigo-600" : "text-slate-500 hover:bg-slate-100")}><Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />{label}</button>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
          <h1 className="text-base font-semibold text-slate-800">{desktopItems.find(i => i.id === activeNav)?.label ?? appName}</h1>
          <div className="w-9" />
        </header>
        <div className="pb-20 md:pb-0">{children}</div>
      </main>

      <nav className="fixed bottom-0 left-0 right-0 z-30 flex md:hidden items-center justify-around border-t border-white/20 bg-white/90 backdrop-blur-xl px-2 py-2" style={{ paddingBottom: "calc(0.5rem + env(safe-area-inset-bottom, 0px))" }}>
        {mobileItems.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => onNavigate(id)} className={cn("flex flex-col items-center gap-0.5 rounded-xl px-3 py-1.5 text-xs transition-colors", activeNav === id ? "text-indigo-500" : "text-slate-400")}><Icon className="h-[18px] w-[18px]" strokeWidth={1.5} /><span>{label}</span></button>
        ))}
      </nav>
    </div>
  );
}
