import {useCallback} from "react";
import {Gauge} from "lucide-react";
import {useGlobalConfig, useSaveGlobalConfig} from "@/hooks/index";
import {useToast} from "@/components/toast-context";
import {Range, Row, Section} from "@/features/sources/sourceConfigForm";

/** 下载与性能：任务级最大并发（书源额度见「书源」页）。 */
export default function DownloadPage() {
  const { data: globalConfig } = useGlobalConfig();
  const saveGlobal = useSaveGlobalConfig();
  const toast = useToast();

  const update = useCallback((key: string, value: unknown) => {
    if (!globalConfig) return;
    saveGlobal.mutateAsync({ ...globalConfig, [key]: value })
      .then(() => toast("设置已保存", "success"))
      .catch(() => toast("设置保存失败", "error"));
  }, [globalConfig, saveGlobal, toast]);

  if (!globalConfig) return null;

  return (
    <Section icon={Gauge} title="并发与性能">
      <Row label="最大下载任务数" desc="同时下载几本书；超出的任务会排队等待">
        <Range value={globalConfig.max_workers} onChange={v => update("max_workers", v)} min={1} max={10} left="1" right="10" />
      </Row>
      <Row label="提示" desc="💡 单本书源的请求并发由该书源「并发数」单独控制（默认 1）"><span /></Row>
    </Section>
  );
}
