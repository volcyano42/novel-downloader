import {useState} from "react";
import {Package} from "lucide-react";
import {useFormatConfig, useSaveFormatConfig} from "@/hooks/index";
import {Num, Row, Section, Select, Toggle} from "@/features/sources/sourceConfigForm";

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
