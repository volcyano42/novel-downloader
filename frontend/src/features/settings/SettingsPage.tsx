import {useCallback, useMemo, useState} from "react";
import {Bell, Gauge, Layers, Package} from "lucide-react";
import {
    useFormatConfig,
    useSaveFormatConfig,
    useSaveGlobalConfig,
    useSources
} from "@/hooks/index";
import {useToast} from "@/components/toast-context";
import type {GlobalConfig} from "@/api/endpoints";
import {Num, Range, Row, Section, Select, Toggle} from "@/features/sources/sourceConfigForm";
import {SourceAccordion} from "@/features/sources/SourceAccordion";

/** 书源：每源一个折叠条，展开即编辑（含逐能力 mode 下拉）。 */
function SourceSection() {
  const { data: sources } = useSources();
  const names = useMemo(() => (sources ? Object.keys(sources) : []), [sources]);

  return (
    <Section icon={Layers} title="书源">
      {names.map(name => <SourceAccordion key={name} name={name} info={sources![name]} />)}
      {names.length === 0 && <div className="py-3 text-xs text-slate-400">暂无书源</div>}
    </Section>
  );
}

const FORMAT_TABS = [
  { id: "txt", label: "TXT" },
  { id: "epub", label: "EPUB" },
  { id: "img", label: "IMG" },
] as const;

function FormatsSection() {
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
      {tab === "txt" && (
        <Row label="编码">
          <Select value={String(fmtCfg?.encoding ?? "utf-8")} onChange={v => saveFmt.mutate({ ...fmtCfg, encoding: v })}
            options={[{ value: "utf-8", label: "UTF-8" }, { value: "gbk", label: "GBK" }]} />
        </Row>
      )}
      {tab === "epub" && (
        <>
          <Row label="压缩算法">
            <Select value={String(fmtCfg?.compression ?? "deflate")} onChange={v => saveFmt.mutate({ ...fmtCfg, compression: v })}
              options={[{ value: "deflate", label: "Deflate" }, { value: "bzip2", label: "BZip2" }, { value: "stored", label: "Stored" }]} />
          </Row>
          <Row label="压缩级别"><Num value={Number(fmtCfg?.compresslevel) || 9} onChange={v => saveFmt.mutate({ ...fmtCfg, compresslevel: v })} min={1} max={9} /></Row>
          <Row label="优化图片"><Toggle checked={!!fmtCfg?.optimize_images} onChange={v => saveFmt.mutate({ ...fmtCfg, optimize_images: v })} /></Row>
          <Row label="JPEG 质量"><Num value={Number(fmtCfg?.jpeg_quality) || 85} onChange={v => saveFmt.mutate({ ...fmtCfg, jpeg_quality: v })} min={1} max={100} /></Row>
          <Row label="最大图宽"><Num value={Number(fmtCfg?.max_image_width) || 0} onChange={v => saveFmt.mutate({ ...fmtCfg, max_image_width: v })} min={0} max={4096} unit="px" /></Row>
          <Row label="包含目录"><Toggle checked={!!fmtCfg?.include_toc} onChange={v => saveFmt.mutate({ ...fmtCfg, include_toc: v })} /></Row>
        </>
      )}
      {tab === "img" && (
        <Row label="输出格式">
          <Select value={String(fmtCfg?.output_format ?? "original")} onChange={v => saveFmt.mutate({ ...fmtCfg, output_format: v })}
            options={[{ value: "original", label: "原始" }, { value: "jpeg", label: "JPEG" }, { value: "png", label: "PNG" }, { value: "webp", label: "WebP" }]} />
        </Row>
      )}
    </Section>
  );
}

interface SettingsViewProps {
  globalConfig: GlobalConfig;
  onUpdate: (path: string, value: unknown) => void;
}

export function SettingsView({ globalConfig, onUpdate }: SettingsViewProps) {
  const saveGlobal = useSaveGlobalConfig();
  const toast = useToast();

  const updateGlobal = useCallback((key: string, value: unknown) => {
    saveGlobal.mutateAsync({ ...globalConfig, [key]: value })
      .then(() => toast("设置已保存", "success"))
      .catch(() => toast("设置保存失败", "error"));
    onUpdate(key, value);
  }, [globalConfig, saveGlobal, onUpdate, toast]);

  return (
    <div className="mx-auto max-w-[640px] space-y-4">
      <SourceSection />

      <Section icon={Gauge} title="并发与性能">
        <Row label="并发线程数" desc="同时下载的章节数">
          <Range value={globalConfig.max_workers} onChange={v => updateGlobal("max_workers", v)} min={1} max={10} left="1" right="10" />
        </Row>
        <Row label="提示" desc="💡 建议 3-5，Browser 模式建议 1-3，过高触发反爬拦截"><span /></Row>
      </Section>

      <FormatsSection />

      <Section icon={Bell} title="通知">
        <Row label="下载完成时" desc="全部章节下载成功时触发">
          <Toggle checked={globalConfig.notify?.on_complete ?? true} onChange={v => updateGlobal("notify", { ...globalConfig.notify, on_complete: v })} />
        </Row>
        <Row label="有不完整章节时" desc="部分章节失败或缺失时触发">
          <Toggle checked={globalConfig.notify?.on_incomplete ?? true} onChange={v => updateGlobal("notify", { ...globalConfig.notify, on_incomplete: v })} />
        </Row>
        <Row label="提示音" desc="bell=终端响铃, system=系统通知, none=静默">
          <Select value={globalConfig.notify?.sound ?? "bell"} onChange={v => updateGlobal("notify", { ...globalConfig.notify, sound: v })}
            options={[{ value: "bell", label: "🔔 响铃" }, { value: "system", label: "💻 系统通知" }, { value: "none", label: "🔇 静默" }]} />
        </Row>
      </Section>
    </div>
  );
}
