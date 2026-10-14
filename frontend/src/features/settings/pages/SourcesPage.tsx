import {useMemo} from "react";
import {Layers} from "lucide-react";
import {useSources} from "@/hooks/index";
import {Section} from "@/features/sources/sourceConfigForm";
import {SourceAccordion} from "@/features/sources/SourceAccordion";

/** 书源：每源一个折叠条，展开即编辑（含逐能力 mode 下拉）。 */
export default function SourcesPage() {
  const { data: sources } = useSources();
  const names = useMemo(() => (sources ? Object.keys(sources) : []), [sources]);

  return (
    <Section icon={Layers} title="书源">
      {names.map(name => <SourceAccordion key={name} name={name} info={sources![name]} />)}
      {names.length === 0 && <div className="py-3 text-xs text-slate-400">暂无书源</div>}
    </Section>
  );
}
