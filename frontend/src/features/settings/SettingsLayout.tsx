import {NavLink, Outlet} from "react-router-dom";
import {Bell, Gauge, Layers, Package} from "lucide-react";
import {cn} from "@/lib/utils";

const ITEMS = [
  { to: "/settings/sources", label: "书源", icon: Layers },
  { to: "/settings/download", label: "下载与性能", icon: Gauge },
  { to: "/settings/export", label: "导出格式", icon: Package },
  { to: "/settings/notify", label: "通知", icon: Bell },
] as const;

/** 设置内二级导航：宽屏为左侧栏，窄屏（< md）为顶部横向滚动标签条。 */
export default function SettingsLayout() {
  return (
    <div className="mx-auto max-w-[1440px] px-6 pt-12 pb-8 md:px-12">
      <div className="flex flex-col gap-6 md:flex-row md:gap-10">
        <nav className="flex shrink-0 gap-1.5 overflow-x-auto md:w-44 md:flex-col md:overflow-visible">
          {ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to}
              className={({ isActive }) => cn(
                "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-indigo-50 font-medium text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-400"
                  : "text-slate-500 hover:bg-slate-50 dark:text-slate-400",
              )}>
              <Icon className="h-4 w-4" strokeWidth={2} />
              <span className="whitespace-nowrap">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="min-w-0 flex-1 space-y-4 md:max-w-[640px]" data-testid="settings-outlet">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
