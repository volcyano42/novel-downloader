import {useState} from "react";
import {ChevronDown} from "lucide-react";
import {cn} from "@/lib/utils";
import type {SourceInfo} from "@/api/endpoints";
import {SourceConfigEditor} from "./sourceConfigForm";
import {CAP_LABELS} from "./sourceConfigFields";

/** 单个书源的折叠条：顶部显示「别名（未设则 source_name）+ 分组 + 能力」；展开即编辑。
 *
 * 启用开关已随 `enabled` 废弃删除；本组件不再有任何开关语义。 */
export function SourceAccordion({ name, info }: { name: string; info: SourceInfo }) {
  const [open, setOpen] = useState(false);
  const display = info.source_alias || name;
  const caps = info.capabilities ?? {};

  return (
    <div className="border-b border-slate-100 last:border-b-0 dark:border-slate-800/50">
      <div className="flex items-center justify-between gap-4 py-2.5">
        <button onClick={() => setOpen(o => !o)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform duration-200", open && "rotate-180")} strokeWidth={1.5} />
          <span className="shrink-0 text-sm font-medium text-slate-700 dark:text-slate-200">{display}</span>
          {info.source_alias && <span className="shrink-0 font-mono text-[10px] text-slate-400">{name}</span>}
          {info.source_group && (
            <span className="shrink-0 rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-500 dark:bg-indigo-500/15 dark:text-indigo-400">{info.source_group}</span>
          )}
          <span className="flex flex-wrap gap-1">
            {Object.keys(caps).length === 0 && <span className="text-[11px] text-slate-400">无能力</span>}
            {Object.entries(caps).map(([cap, mode]) => (
              <span key={cap} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {CAP_LABELS[cap] ?? cap}·{mode}
              </span>
            ))}
          </span>
        </button>
      </div>
      {open && <SourceConfigEditor name={name} />}
    </div>
  );
}
