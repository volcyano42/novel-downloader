import {useCallback, useState} from "react";
import {CircleAlert, CircleCheck, Loader2, RefreshCw, X} from "lucide-react";
import {useCancelSync, useStartSync, useSyncStatus} from "@/hooks/index";
import {useToast} from "@/components/toast-context";
import {Row, Section} from "@/features/sources/sourceConfigForm";

const PEER_KEY = "sync-peer-url";

/** 从另一台设备拉取本地缺失的章节（只补缺，不覆盖）。 */
export default function SyncPage() {
  const [peer, setPeer] = useState(() => localStorage.getItem(PEER_KEY) ?? "");
  const [includeImages, setIncludeImages] = useState(false);

  const { data: status } = useSyncStatus();
  const startMut = useStartSync();
  const cancelMut = useCancelSync();
  const toast = useToast();

  const running = status?.running ?? false;

  const handleStart = useCallback(() => {
    const target = peer.trim();
    if (!target) {
      toast("请先填写对端地址", "error");
      return;
    }
    localStorage.setItem(PEER_KEY, target);
    startMut.mutateAsync({ peer: target, include_images: includeImages })
      .then(() => toast("已开始同步", "success"))
      .catch((e: Error) => toast(e.message || "启动失败", "error"));
  }, [peer, includeImages, startMut, toast]);

  const handleCancel = useCallback(() => {
    cancelMut.mutateAsync()
      .then(() => toast("已请求取消", "success"))
      .catch(() => toast("取消失败", "error"));
  }, [cancelMut, toast]);

  return (
    <div className="space-y-4">
      <Section icon={RefreshCw} title="从其他设备同步">
        <Row label="对端地址" desc="另一台设备的地址，如 192.168.1.20:8000（对端需已启动）">
          <input
            value={peer}
            onChange={e => setPeer(e.target.value)}
            placeholder="192.168.1.20:8000"
            disabled={running}
            className="w-48 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700 outline-none transition-colors focus:border-indigo-400 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          />
        </Row>
        <Row label="连封面和插图一起拉" desc="体积可能很大（GB 级），一般只拉正文即可">
          <input
            type="checkbox"
            checked={includeImages}
            onChange={e => setIncludeImages(e.target.checked)}
            disabled={running}
            className="h-4 w-4 accent-indigo-500"
          />
        </Row>
        <div className="flex items-center justify-end gap-2 pt-2">
          {running ? (
            <button
              onClick={handleCancel}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300"
            >
              <X className="h-3.5 w-3.5" strokeWidth={2} />取消
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={startMut.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-600 disabled:opacity-40"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${startMut.isPending ? "animate-spin" : ""}`} strokeWidth={2} />
              开始同步
            </button>
          )}
        </div>
      </Section>

      {status && <StatusCard status={status} />}
    </div>
  );
}

function StatusCard({ status }: { status: NonNullable<ReturnType<typeof useSyncStatus>["data"]> }) {
  const pct = (() => {
    if (status.chapters_total > 0) return Math.round((status.chapters_done / status.chapters_total) * 100);
    if (status.books_total > 0) return Math.round((status.books_done / status.books_total) * 100);
    return 0;
  })();

  const label = (() => {
    switch (status.phase) {
      case "scanning":
        return status.books_total
          ? `扫描书单 ${status.books_done}/${status.books_total}`
          : "正在连接对端…";
      case "pulling":
        return `拉取章节 ${status.chapters_done}/${status.chapters_total}`;
      case "done":
        return "同步完成";
      case "cancelled":
        return "已取消（已写入的章节保留）";
      case "error":
        return "同步失败";
      default:
        return status.phase;
    }
  })();

  const tone = status.phase === "error"
    ? "text-rose-500"
    : status.phase === "done"
      ? "text-emerald-500"
      : "text-indigo-500";

  return (
    <section className="rounded-2xl border border-white/20 bg-white/80 p-5 shadow-card backdrop-blur-xl dark:border-slate-700/30 dark:bg-slate-900/80">
      <div className="flex items-center gap-2">
        {status.running
          ? <Loader2 className={`h-4 w-4 animate-spin ${tone}`} strokeWidth={2} />
          : status.phase === "done"
            ? <CircleCheck className={`h-4 w-4 ${tone}`} strokeWidth={2} />
            : <CircleAlert className={`h-4 w-4 ${tone}`} strokeWidth={2} />}
        <span className={`text-sm font-medium ${tone}`}>{label}</span>
        <span className="ml-auto truncate text-[11px] text-slate-400">{status.peer}</span>
      </div>

      {status.running && (
        <>
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
            <div className="h-full rounded-full bg-indigo-500 transition-all duration-300" style={{ width: `${pct}%` }} />
          </div>
          <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-400">
            <span className="truncate">{status.current_book}{status.current_chapter ? ` · ${status.current_chapter}` : ""}</span>
            <span className="ml-auto shrink-0 tabular-nums">{pct}%</span>
          </div>
        </>
      )}

      {status.summary && !status.running && (
        <p className="mt-3 text-xs leading-relaxed text-slate-600 dark:text-slate-300">{status.summary}</p>
      )}

      {status.error && (
        <p className="mt-3 break-words text-xs leading-relaxed text-rose-500">{status.error}</p>
      )}

      {status.order_mismatch && status.order_mismatch.length > 0 && (
        <p className="mt-2 text-[11px] leading-relaxed text-amber-600 dark:text-amber-500">
          章节序号与对端不一致，已跳过：{status.order_mismatch.join("、")}
        </p>
      )}
    </section>
  );
}
