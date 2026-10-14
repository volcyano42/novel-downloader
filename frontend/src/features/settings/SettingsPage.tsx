import type {GlobalConfig} from "@/api/endpoints";
import SourcesPage from "@/features/settings/pages/SourcesPage";
import DownloadPage from "@/features/settings/pages/DownloadPage";
import ExportPage from "@/features/settings/pages/ExportPage";
import NotifyPage from "@/features/settings/pages/NotifyPage";

interface SettingsViewProps {
  globalConfig: GlobalConfig;
  onUpdate: (path: string, value: unknown) => void;
}

/** 过渡聚合视图：Task 3 起由 SettingsLayout + 子路由取代（保留 props 以免 BookshelfPage 报错）。 */
export function SettingsView(_props: SettingsViewProps) {
  return (
    <div className="mx-auto max-w-[640px] space-y-4">
      <SourcesPage />
      <DownloadPage />
      <ExportPage />
      <NotifyPage />
    </div>
  );
}
