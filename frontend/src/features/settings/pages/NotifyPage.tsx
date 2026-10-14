import {useCallback} from "react";
import {Bell} from "lucide-react";
import {useGlobalConfig, useSaveGlobalConfig} from "@/hooks/index";
import {useToast} from "@/components/toast-context";
import {Row, Section, Select, Toggle} from "@/features/sources/sourceConfigForm";

/** 通知：下载完成 / 有不完整章节时的提醒与提示音。 */
export default function NotifyPage() {
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
    <Section icon={Bell} title="通知">
      <Row label="下载完成时" desc="全部章节下载成功时触发">
        <Toggle checked={globalConfig.notify?.on_complete ?? true} onChange={v => update("notify", { ...globalConfig.notify, on_complete: v })} />
      </Row>
      <Row label="有不完整章节时" desc="部分章节失败或缺失时触发">
        <Toggle checked={globalConfig.notify?.on_incomplete ?? true} onChange={v => update("notify", { ...globalConfig.notify, on_incomplete: v })} />
      </Row>
      <Row label="提示音" desc="bell=终端响铃, system=系统通知, none=静默">
        <Select value={globalConfig.notify?.sound ?? "bell"} onChange={v => update("notify", { ...globalConfig.notify, sound: v })}
          options={[{ value: "bell", label: "🔔 响铃" }, { value: "system", label: "💻 系统通知" }, { value: "none", label: "🔇 静默" }]} />
      </Row>
    </Section>
  );
}
