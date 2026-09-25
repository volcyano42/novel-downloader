import {useEffect, useMemo, useState} from "react";
import {ChevronDown, Layers} from "lucide-react";
import {cn} from "@/lib/utils";
import {useSaveSourceConfig, useSources} from "@/hooks/index";
import {CAP_LABELS, Section, SourceConfigEditor, Toggle} from "./sourceConfigForm";

/** 列表单行：书源名 + 能力摘要 + enabled 开关 + 编辑配置入口。 */
function SourceRow({ name, info }: { name: string; info: { capabilities: Record<string, string>; enabled: boolean } }) {
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
    <div className="py-1">
      <div className="flex items-center justify-between gap-4 py-1.5">
        <div className="min-w-0">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{name}</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {Object.keys(caps).length === 0 && <span className="text-[11px] text-slate-400">无能力</span>}
            {Object.entries(caps).map(([cap, mode]) => (
              <span key={cap} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {CAP_LABELS[cap] ?? cap}·{mode}
              </span>
            ))}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Toggle checked={enabled} onChange={toggleEnabled} />
          <button onClick={() => setOpen(o => !o)}
            className="flex items-center gap-1 text-xs font-medium text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-200", open && "rotate-180")} strokeWidth={1.5} />
            编辑配置
          </button>
        </div>
      </div>
      {open && <SourceConfigEditor name={name} />}
    </div>
  );
}

export default function SourcesPage() {
  const { data: sources } = useSources();
  const names = useMemo(() => (sources ? Object.keys(sources) : []), [sources]);

  return (
    <div className="px-6 pt-12 pb-8 md:px-12">
      <div className="mx-auto max-w-[720px] space-y-4">
        <Section icon={Layers} title="书源管理">
          {names.map(name => (
            <SourceRow key={name} name={name} info={sources![name]} />
          ))}
          {names.length === 0 && <div className="py-3 text-xs text-slate-400">暂无书源</div>}
        </Section>
      </div>
    </div>
  );
}
