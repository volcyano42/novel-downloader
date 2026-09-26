import {useEffect, useState} from "react";
import {ChevronDown} from "lucide-react";
import {cn} from "@/lib/utils";
import {useSaveSourceConfig, useSourceConfig} from "@/hooks/index";
import {SourceConfigEditor, Toggle} from "./sourceConfigForm";
import {CAP_LABELS} from "./sourceConfigFields";

/** 单个书源的折叠条：名称 + 能力 badge + enabled 开关 + 书源级并发数；展开即编辑配置（含 mode 下拉）。 */
export function SourceAccordion({ name, info }: { name: string; info: { capabilities: Record<string, string>; enabled: boolean } }) {
  const saveSource = useSaveSourceConfig(name);
  const { data: cfg } = useSourceConfig(name);
  const [enabled, setEnabled] = useState(info.enabled);
  const [open, setOpen] = useState(false);
  // 并发数输入用字符串保存，失焦时校验提交（非法值不写）；回车只触发失焦，
  // 由 onBlur 统一提交一次，避免 Enter+blur 连发两次相同 PUT
  const [concurrency, setConcurrency] = useState("1");

  // 列表数据（useSources）刷新后同步开关显示
  useEffect(() => { setEnabled(info.enabled); }, [info.enabled]);
  // 服务端并发额度（保存成功后 refetch）刷新后同步输入框
  useEffect(() => { setConcurrency(String(cfg?.concurrency ?? 1)); }, [cfg?.concurrency]);

  const caps = info.capabilities ?? {};
  const toggleEnabled = (v: boolean) => {
    setEnabled(v); // 乐观更新，避免受控开关因 refetch 滞后回弹
    saveSource.mutate({ enabled: v });
  };

  const commitConcurrency = () => {
    const n = Number(concurrency);
    if (!Number.isInteger(n) || n < 1) { // 非法：回滚显示，不提交
      setConcurrency(String(cfg?.concurrency ?? 1));
      return;
    }
    if (n !== (cfg?.concurrency ?? 1)) saveSource.mutate({ concurrency: n });
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
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-slate-400">并发数</span>
            <input
              type="number" min={1} step={1}
              value={concurrency}
              onChange={e => setConcurrency(e.target.value)}
              onBlur={commitConcurrency}
              onKeyDown={e => { if (e.key === "Enter") e.currentTarget.blur(); }}
              className="w-14 rounded-lg border border-white/20 bg-white/50 px-2 py-1 text-right text-xs text-slate-700 outline-none backdrop-blur-sm dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-300"
            />
          </div>
          <Toggle checked={enabled} onChange={toggleEnabled} />
        </div>
      </div>
      {open && <SourceConfigEditor name={name} />}
    </div>
  );
}
