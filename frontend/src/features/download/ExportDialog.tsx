/**
 * 导出弹窗：左侧导航（格式 / 章节范围 / 导出选项）+ 右侧内容。
 *
 * 两条硬约束（见 docs/superpowers/specs/2026-10-26-export-chapter-selection-design.md）：
 * 1. **章节必须是显式选择**：后端 `if body.chapter_id:` 会把空数组当「未指定」→ 静默导出整本。
 *    所以空选择时按钮禁用，提交前还有一道断言兜底。
 * 2. **导出参数是临时的**：不调 useSaveFormatConfig、不 mutate 任何 query key、
 *    不读写 localStorage/sessionStorage。初始值只从 useFormatConfig 读一次快照。
 */

import {useCallback, useEffect, useMemo, useState} from "react";
import {Check, FileDown, ListOrdered, Loader2, Settings2} from "lucide-react";
import {cn} from "@/lib/utils";
import {useFormatConfig} from "@/hooks/index";
import {useToast} from "@/components/toast-context";
import {ExportOptionsFields} from "@/features/sources/sourceConfigForm";
import {ChapterRangePicker} from "./ChapterRangePicker";

const FORMATS = [
  { id: "txt", label: "TXT", desc: "纯文本" },
  { id: "epub", label: "EPUB", desc: "电子书" },
  { id: "img", label: "IMG", desc: "小说插图" },
] as const;

type FormatId = (typeof FORMATS)[number]["id"];
type TabId = "format" | "chapters" | "options";

const TABS = [
  { id: "format", label: "格式", icon: FileDown },
  { id: "chapters", label: "章节范围", icon: ListOrdered },
  { id: "options", label: "导出选项", icon: Settings2 },
] as const;

export interface ExportDialogResult {
  formats: string[];
  /** 非空 —— 空数组会被后端当成「未指定」而导出整本 */
  chapterIds: string[];
  options: Partial<Record<FormatId, Record<string, unknown>>>;
}

interface ExportDialogProps {
  open: boolean;
  onClose: () => void;
  novelId: string;
  novelTitle: string;
  onExport: (result: ExportDialogResult) => void;
}

export function ExportDialog({ open, onClose, novelId, novelTitle, onExport }: ExportDialogProps) {
  const [tab, setTab] = useState<TabId>("chapters");
  const [format, setFormat] = useState<FormatId>("txt");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  /** 仅本次导出有效的参数副本；键缺省表示「沿用该格式配置」 */
  const [draft, setDraft] = useState<Partial<Record<FormatId, Record<string, unknown>>>>({});

  const { data: txtCfg } = useFormatConfig("txt");
  const { data: epubCfg } = useFormatConfig("epub");
  const { data: imgCfg } = useFormatConfig("img");
  const toast = useToast();

  const savedCfg = useMemo<Record<FormatId, Record<string, unknown>>>(
    () => ({
      txt: (txtCfg ?? {}) as Record<string, unknown>,
      epub: (epubCfg ?? {}) as Record<string, unknown>,
      img: (imgCfg ?? {}) as Record<string, unknown>,
    }),
    [txtCfg, epubCfg, imgCfg],
  );

  // 打开时重置：选择清空、参数回到「沿用保存值」、回到章节栏
  useEffect(() => {
    if (!open) return;
    setTab("chapters");
    setSelected(new Set());
    setDraft({});
    setLoading(false);
  }, [open]);

  const currentOptions = draft[format] ?? savedCfg[format];

  const handleOptionsChange = useCallback(
    (patch: Record<string, unknown>) => {
      setDraft(prev => ({ ...prev, [format]: { ...(prev[format] ?? savedCfg[format]), ...patch } }));
    },
    [format, savedCfg],
  );

  const chapterIds = useMemo(() => [...selected], [selected]);
  const canExport = chapterIds.length > 0 && !loading;

  const handleExport = useCallback(() => {
    // 断言式兜底：按钮禁用之外的第二次拦截，绝不让空数组走到请求
    if (chapterIds.length === 0) {
      toast("请先选择至少一个已下载章节", "error");
      return;
    }
    setLoading(true);
    onExport({ formats: [format], chapterIds, options: { [format]: currentOptions } });
  }, [chapterIds, format, currentOptions, onExport, toast]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overscroll-contain bg-black/40 backdrop-blur-sm"
      onClick={onClose}>
      <div
        onClick={e => e.stopPropagation()}
        className="flex h-[88vh] w-[95vw] flex-col overflow-hidden rounded-2xl border border-white/20 bg-white/95 shadow-2xl backdrop-blur-xl animate-in zoom-in-95 fade-in duration-200 dark:bg-slate-900/95 sm:h-[520px] sm:w-[720px] sm:max-w-[95vw] sm:flex-row">
        {/* 左栏导航 */}
        <nav className="flex shrink-0 gap-0.5 border-b border-white/20 bg-white/50 p-2 dark:border-slate-700/30 dark:bg-slate-900/60 sm:w-36 sm:flex-col sm:border-b-0 sm:border-r sm:p-2.5">
          <div className="hidden px-2 pb-2 pt-1 sm:block">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">导出</h2>
            <p className="truncate text-[11px] text-slate-400">{novelTitle}</p>
          </div>
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={cn(
                "flex flex-1 items-center justify-center gap-2 rounded-lg px-2 py-2 text-xs transition-colors sm:flex-none sm:justify-start sm:px-2.5 sm:text-left",
                tab === id
                  ? "bg-indigo-50 font-medium text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-400"
                  : "text-slate-600 hover:bg-slate-100/70 dark:text-slate-300 dark:hover:bg-slate-800/60",
              )}>
              <Icon className="h-3.5 w-3.5 shrink-0" strokeWidth={1.8} />
              {label}
            </button>
          ))}
        </nav>

        {/* 右栏内容 */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 overflow-hidden p-3 sm:p-4">
            {tab === "format" && (
              <div className="space-y-2">
                {FORMATS.map(({ id, label, desc }) => {
                  const checked = format === id;
                  return (
                    <button
                      key={id}
                      onClick={() => setFormat(id)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all",
                        checked
                          ? "border-indigo-300 bg-indigo-50 dark:border-indigo-500/40 dark:bg-indigo-500/15"
                          : "border-white/20 bg-white/60 hover:border-slate-200 dark:border-slate-700/30 dark:bg-slate-800/50",
                      )}>
                      <span
                        className={cn(
                          "flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition-colors",
                          checked ? "border-indigo-500 bg-indigo-500" : "border-slate-300",
                        )}>
                        {checked && <Check className="h-3 w-3 text-white" strokeWidth={3} />}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className={cn("text-sm font-medium", checked ? "text-indigo-600 dark:text-indigo-400" : "text-slate-700 dark:text-slate-200")}>{label}</span>
                        <span className="block text-[11px] text-slate-400">{desc}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            )}

            {tab === "chapters" && (
              <ChapterRangePicker novelId={novelId} selected={selected} onChange={setSelected} />
            )}

            {tab === "options" && (
              <div className="h-full overflow-y-auto">
                <ExportOptionsFields
                  format={format}
                  value={currentOptions}
                  onChange={handleOptionsChange}
                />
                <p className="pt-2 text-[11px] text-slate-400">
                  这里的修改只对本次导出生效，不会写回设置里的导出格式配置。
                </p>
              </div>
            )}
          </div>

          {/* 底部操作区 */}
          <div className="flex shrink-0 items-center gap-1.5 border-t border-white/20 px-3 py-2.5 dark:border-slate-700/30 sm:gap-2 sm:px-4 sm:py-3">
            <span className="hidden min-w-0 flex-1 truncate text-[11px] text-slate-400 sm:inline">
              已选 <span className="font-medium text-indigo-500">{chapterIds.length}</span> 章 · {format.toUpperCase()}
            </span>
            <button
              onClick={onClose}
              className="flex-1 rounded-xl border border-white/20 bg-white/60 px-4 py-2.5 text-xs text-slate-500 transition-colors hover:bg-slate-50 dark:border-slate-700/30 dark:bg-slate-800/50 dark:text-slate-300 sm:flex-none sm:py-2">
              取消
            </button>
            <button
              onClick={handleExport}
              disabled={!canExport}
              title={chapterIds.length === 0 ? "请至少选择一个已下载章节" : undefined}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-indigo-500 px-4 py-2.5 text-xs font-medium text-white transition-colors hover:bg-indigo-600 disabled:cursor-not-allowed disabled:opacity-50 sm:flex-none sm:py-2">
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} /> : <FileDown className="h-3.5 w-3.5" strokeWidth={2} />}
              {loading ? "导出中…" : "开始导出"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
