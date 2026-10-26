import {useState} from "react";
import {Package} from "lucide-react";
import {useFormatConfig, useSaveFormatConfig} from "@/hooks/index";
import {ExportOptionsFields, Section} from "@/features/sources/sourceConfigForm";

const FORMAT_TABS = [
  { id: "txt", label: "TXT" },
  { id: "epub", label: "EPUB" },
  { id: "img", label: "IMG" },
] as const;

/** 导出格式：按格式分 tab 编辑出厂配置。 */
export default function ExportPage() {
  const [tab, setTab] = useState("txt");
  const { data: fmtCfg } = useFormatConfig(tab);
  const saveFmt = useSaveFormatConfig(tab);

  return (
    <Section icon={Package} title="导出格式">
      <div className="flex gap-1.5 py-2.5">
        {FORMAT_TABS.map(({ id, label }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium uppercase transition-all ${tab === id ? "border-indigo-300 bg-indigo-50 text-indigo-600 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-400" : "border-white/20 bg-white/50 text-slate-500 hover:border-slate-200 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-400"}`}>
            {label}
          </button>
        ))}
      </div>
      <ExportOptionsFields
        format={tab as "txt" | "epub" | "img"}
        value={(fmtCfg ?? {}) as Record<string, unknown>}
        onChange={patch => saveFmt.mutate({ ...fmtCfg, ...patch })}
      />
    </Section>
  );
}
