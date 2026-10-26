/**
 * 章节范围选择器：SSE 列表 + 范围输入框 + 快捷选择 + 搜索。
 *
 * 设计约束（见 docs/superpowers/specs/2026-10-26-export-chapter-selection-design.md §4）：
 * - 列表复用详情页那条 SSE，先用 sessionStorage 缓存回填再增量合并；
 *   **不写回**缓存（写入职责留在详情页，避免弹窗污染主窗口的缓存内容）。
 * - 输入框表达**完整选中集合**（覆盖语义），勾选变化时回写规范化文本。
 * - 未下载章节（`downloaded === false`）标灰且不可勾选。
 * - 状态全由外部持有（受控组件），弹窗关闭即随之丢弃。
 */

import {memo, useCallback, useEffect, useMemo, useRef, useState} from "react";
import {Check, ChevronDown, Loader2} from "lucide-react";
import {cn} from "@/lib/utils";
import {streamChapters, type ChapterBrief} from "@/api/endpoints";
import {getCachedChapters} from "@/utils/chapterCache";
import {formatIdsAsRanges, parseRangesToIds} from "./chapterRange";

interface ChapterRangePickerProps {
  novelId: string;
  /** 已选章节 id 集合（受控） */
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}

/** 输入即解析的防抖间隔 */
const PARSE_DEBOUNCE_MS = 150;

export function ChapterRangePicker({ novelId, selected, onChange }: ChapterRangePickerProps) {
  const [chapters, setChapters] = useState<ChapterBrief[]>([]);
  const [streaming, setStreaming] = useState(true);
  const [streamError, setStreamError] = useState(false);
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState(false);

  /** 用户正在输入时不要用回写打断光标 */
  const typingRef = useRef(false);
  const debounceRef = useRef<number | null>(null);

  // ── 章节列表：缓存回填 + SSE 增量 ──────────────────────────
  useEffect(() => {
    const cached = getCachedChapters(novelId);
    if (cached?.length) {
      setChapters(cached);
      setStreaming(false);
    } else {
      setChapters([]);
      setStreaming(true);
    }
    setStreamError(false);

    const ac = new AbortController();
    const acc: ChapterBrief[] = [];
    streamChapters(
      novelId,
      ch => {
        acc.push(ch);
        setChapters(prev => [...prev, ch]);
      },
      () => setStreaming(false),
      () => {
        setStreamError(true);
        setStreaming(false);
      },
      ac.signal,
    );
    return () => ac.abort();
  }, [novelId]);

  // ── 选中集合 → 输入框回写 ─────────────────────────────────
  useEffect(() => {
    if (typingRef.current) return;
    setText(formatIdsAsRanges([...selected], chapters));
  }, [selected, chapters]);

  // ── 输入框 → 选中集合（覆盖语义，防抖）─────────────────────
  const applyText = useCallback(
    (raw: string) => onChange(new Set(parseRangesToIds(raw, chapters))),
    [chapters, onChange],
  );

  const handleTextChange = useCallback(
    (raw: string) => {
      setText(raw);
      typingRef.current = true;
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
      debounceRef.current = window.setTimeout(() => {
        applyText(raw);
        typingRef.current = false;
        debounceRef.current = null;
      }, PARSE_DEBOUNCE_MS);
    },
    [applyText],
  );

  useEffect(
    () => () => {
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    },
    [],
  );

  // ── 快捷选择 ─────────────────────────────────────────────
  const downloadedIds = useMemo(
    () => chapters.filter(c => c.downloaded).map(c => c.id),
    [chapters],
  );

  const selectAll = useCallback(() => onChange(new Set(downloadedIds)), [downloadedIds, onChange]);
  const clearAll = useCallback(() => onChange(new Set()), [onChange]);
  const invert = useCallback(() => {
    const next = new Set<string>();
    for (const id of downloadedIds) if (!selected.has(id)) next.add(id);
    onChange(next);
  }, [downloadedIds, selected, onChange]);

  // ── 行勾选 ───────────────────────────────────────────────
  const toggle = useCallback(
    (id: string) => {
      const next = new Set(selected);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      onChange(next);
    },
    [selected, onChange],
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return chapters;
    return chapters.filter(c => c.title.toLowerCase().includes(q) || String(c.order).includes(q));
  }, [chapters, query]);

  return (
    <div className="flex h-full min-w-0 flex-col gap-2.5 overflow-hidden">
      {/* 输入框 + 快捷 */}
      <div className="shrink-0 space-y-2">
        <input
          value={text}
          onChange={e => handleTextChange(e.target.value)}
          onBlur={() => {
            typingRef.current = false;
            if (debounceRef.current !== null) {
              window.clearTimeout(debounceRef.current);
              debounceRef.current = null;
              applyText(text);
            }
          }}
          placeholder="章节范围，如 5 / 5-20 / 1 3 5-10"
          className="w-full rounded-lg border border-white/20 bg-white/70 px-3 py-2 text-xs text-slate-700 outline-none placeholder:text-slate-400 focus:border-indigo-300 dark:border-slate-600/30 dark:bg-slate-800/60 dark:text-slate-200"
        />
        <div className="flex flex-wrap items-center gap-1.5">
          <QuickBtn onClick={selectAll}>全选</QuickBtn>
          <QuickBtn onClick={invert}>反选</QuickBtn>
          <QuickBtn onClick={clearAll}>清空</QuickBtn>
          <span className="ml-auto text-[11px] text-slate-400">
            已选 <span className="font-medium text-indigo-500">{selected.size}</span> 章
            {streaming && <Loader2 className="ml-1 inline h-3 w-3 animate-spin" strokeWidth={2} />}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="筛选标题 / 章节号"
            className="min-w-0 flex-1 rounded-lg border border-white/20 bg-white/50 px-2.5 py-1.5 text-[11px] text-slate-600 outline-none placeholder:text-slate-400 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-300"
          />
          <button onClick={() => setCollapsed(v => !v)}
            className="flex shrink-0 items-center gap-0.5 rounded-lg border border-white/20 px-2 py-1.5 text-[11px] text-slate-500 hover:bg-slate-50 dark:border-slate-600/30">
            {collapsed ? "展开" : "收起"}
            <ChevronDown className={cn("h-3 w-3 transition-transform", collapsed && "-rotate-90")} strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* 列表 */}
      {!collapsed && (
        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain rounded-lg border border-white/20 bg-white/40 dark:border-slate-600/30 dark:bg-slate-800/40">
          {visible.length === 0 ? (
            <p className="px-3 py-6 text-center text-[11px] text-slate-400">
              {streamError ? "章节流中断，请关闭重开" : streaming ? "加载中…" : "没有匹配的章节"}
            </p>
          ) : (
            visible.map(ch => (
              <ChapterRow
                key={ch.id}
                chapter={ch}
                checked={selected.has(ch.id)}
                onToggle={toggle}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

function QuickBtn({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick}
      className="rounded-lg border border-white/20 bg-white/60 px-2 py-1 text-[11px] text-slate-600 transition-colors hover:border-indigo-200 hover:text-indigo-600 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-300">
      {children}
    </button>
  );
}

/**
 * 行组件：memo 化，避免千章列表在勾选时全表重渲染。
 *
 * ⚠️ 这里**不能**用 `<label>` + `sr-only` 原生 checkbox：`sr-only` 是
 * `position: absolute` 的 1px 元素，点击 label 让它获得焦点时，浏览器为
 * 「保证聚焦元素可见」会滚动祖先链 —— 列表是 `overflow-y-auto`、弹窗是
 * `fixed` 遮罩，于是点需要滚动才可见的行时**整个界面会偏移**。
 * 项目里所有手绘复选框（ExportDialog 的格式卡、sourceConfigForm 的 Toggle）
 * 都是 `<button>`/`role` 手绘，不用原生 input，此处保持一致。
 */
const ChapterRow = memo(function ChapterRow({ chapter, checked, onToggle }: {
  chapter: ChapterBrief;
  checked: boolean;
  onToggle: (id: string) => void;
}) {
  const disabled = !chapter.downloaded;
  const toggle = () => {
    if (disabled) return; // 未下载：点不动，也不会被程序化选中
    onToggle(chapter.id);
  };
  return (
    <div
      role="checkbox"
      aria-checked={checked}
      aria-disabled={disabled}
      tabIndex={disabled ? -1 : 0}
      onClick={toggle}
      onKeyDown={e => {
        if (disabled) return;
        if (e.key === " " || e.key === "Enter") {
          e.preventDefault(); // 空格默认会滚动页面
          toggle();
        }
      }}
      className={cn(
        "flex items-center gap-2.5 border-b border-white/10 px-3 py-2.5 outline-none last:border-b-0 dark:border-slate-700/20 sm:py-1.5",
        disabled
          ? "cursor-not-allowed opacity-45"
          : "cursor-pointer hover:bg-indigo-50/60 focus-visible:bg-indigo-50/60 dark:hover:bg-indigo-500/10 dark:focus-visible:bg-indigo-500/10",
      )}>
      <span
        className={cn(
          "flex h-4 w-4 shrink-0 items-center justify-center rounded border-2 transition-colors",
          checked ? "border-indigo-500 bg-indigo-500" : "border-slate-300",
        )}>
        {checked && <Check className="h-2.5 w-2.5 text-white" strokeWidth={3} />}
      </span>
      <span className="w-10 shrink-0 text-[11px] tabular-nums text-slate-400">{chapter.order}</span>
      <span className="min-w-0 flex-1 truncate text-xs text-slate-700 dark:text-slate-200">{chapter.title}</span>
      {disabled && <span className="shrink-0 text-[10px] text-slate-400">未下载</span>}
      {!disabled && chapter.image_count > 0 && (
        <span className="shrink-0 text-[10px] text-slate-400">图{chapter.image_count}</span>
      )}
    </div>
  );
});
