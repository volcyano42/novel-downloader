import {useEffect, useState} from "react";
import {ChevronDown} from "lucide-react";
import {cn} from "@/lib/utils";
import {useSaveSourceConfig} from "@/hooks/index";
import {SourceConfigEditor, Toggle} from "./sourceConfigForm";
import {CAP_LABELS} from "./sourceConfigFields";

/** 单个书源的折叠条：名称 + 能力 badge + enabled 开关；展开即编辑配置（含 mode 下拉）。 */
export function SourceAccordion({ name, info }: { name: string; info: { capabilities: Record<string, string>; enabled: boolean } }) {
  const saveSource = useSaveSourceConfig(name);
  const [enabled, setEnabled] = useState(info.enabled);
  const [open, setOpen] = useState(false);

  // 列表数据（useSources）刷新后同步开关显示
  useEffect(() => { setEnabled(info.enabled); }, [info.enabled]);

  const caps = info.capabilities ?? {};
  const toggleEnabled = (v: boolean) => {
    setEnabled(v); // 乐观更新，避免受控开关因 refetch 滞后回弹
    saveSource.mutate({ enabled: v });
  };

  return (
    <div className="border-b border-slate-100 last:border-b-0 dark:border-slate-800/50">
      <div className="flex items-center justify-between gap-4 py-2.5">
        <button onClick={() => setOpen(o => !o)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform duration-200", open && "rotate-180")} strokeWidth={1.5} />
          <span className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{name}</span>
          <span className="flex flex-wrap gap-1">
            {Object.keys(caps).length === 0 && <span className="text-[11px] text-slate-400">无能力</span>}
            {Object.entries(caps).map(([cap, mode]) => (
              <span key={cap} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {CAP_LABELS[cap] ?? cap}·{mode}
              </span>
            ))}
          </span>
        </button>
        <div className="flex shrink-0 items-center gap-3">
          <Toggle checked={enabled} onChange={toggleEnabled} />
        </div>
      </div>
      {open && <SourceConfigEditor name={name} />}
    </div>
  );
}
