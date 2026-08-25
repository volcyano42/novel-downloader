/** 所有 API 端点 + 类型定义 — /api/v2 */

import {apiDelete, apiGet, apiPost, apiPut} from "./client";

// ── Types ──────────────────────────────────────────

export interface NovelMeta {
  title: string; url: string; id: string; serial: number;
  author: string; description: string;
  tags: string[] | null; count: number | null;
  cover: { raw_data: string | null; alt: string | null; url: string | null; format: string | null } | null;
  extra?: { rating?: number } | null;
}

export interface ChapterBrief {
  id: string; url: string; novel_id: string; title: string; order: number;
  volume: string | null; count: number | null; downloaded: boolean; image_count: number;
}

export interface ChapterData extends ChapterBrief {
  content: string | null; time: number | null;
  images: { raw_data: string | null; alt: string | null; insert: number | null; url: string | null }[];
}

export interface SearchResult {
  title: string; author: string; url: string; description: string | null;
  platform: string;
  cover_url?: string | null;
  extra?: { rating?: number } | null;
}

export interface ChapterStatus {
  title: string; order: number; status: "pending" | "downloading" | "downloaded" | "failed";
  error?: string;
}

export interface TaskInfo {
  task_id: string; novel_id: string; title: string; total: number;
  progress: number; status: string; error: string | null; errors: string[];
  current_title: string;
  chapters: ChapterStatus[];
  eta?: number;
}

export interface EngineOptions {
  headless?: boolean; browser_type?: string; user_data_dir?: string;
  viewport?: { width: number; height: number };
  headers?: Record<string, string>; cookies?: Record<string, string>;
  proxies?: Record<string, string>;
  delay: [number, number]; timeout: number;
  retry_times: number; backoff_factor: number;
}

export interface FormatOptions {
  enabled: boolean; output_path?: string; file_name_template?: string;
}

export interface TxtOptions extends FormatOptions { encoding: string; }
export interface EpubOptions extends FormatOptions {
  compression: string; compresslevel: number;
  optimize_images: boolean; jpeg_quality: number;
  max_image_width: number; include_toc: boolean;
  encoding?: string; css_style?: string;
}
export interface ImgOptions extends FormatOptions { output_format: string; }

export interface NotifyConfig {
  on_complete: boolean; on_incomplete: boolean; sound: "bell" | "system" | "none";
}

export interface GlobalConfig {
  mode: string; max_workers: number;
  notify: NotifyConfig;
}

export interface SiteConfig {
  browser: Record<string, EngineOptions>; requests: Record<string, EngineOptions>; api: Record<string, EngineOptions>;
  api_variants: string[];
}

export type GroupsConfig = Record<string, Record<string, object>>;

export interface ExportTaskResult {
  task_id: string; status: string; progress: number;
  formats?: string[]; path?: string | null; error?: string | null;
}

export interface EngineInfo {
  id: string; mode: string; platform: string;
}

// ── Storage ────────────────────────────────────────

export function listNovels(signal?: AbortSignal) {
  return apiGet<NovelMeta[]>("/storage/novel", signal);
}

export function getMeta(novelId: string) {
  return apiGet<NovelMeta>(`/storage/novel/${novelId}/meta`);
}

export function deleteNovel(novelId: string) {
  return apiDelete(`/storage/novel/${novelId}`);
}

export function listChapters(
  novelId: string,
  params?: { order?: string; page?: number; size?: number },
  signal?: AbortSignal,
) {
  const qs = new URLSearchParams();
  if (params?.order) qs.set("order", params.order);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.size) qs.set("size", String(params.size));
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiGet<ChapterBrief[]>(`/storage/novel/${novelId}/chapters${suffix}`, signal);
}

export function getChapter(novelId: string, chapterId: string) {
  return apiGet<ChapterData>(`/storage/novel/${novelId}/chapter/${chapterId}`);
}

export function streamChapters(
  novelId: string,
  onChapter: (ch: ChapterBrief) => void,
  onDone: () => void,
  onError: () => void,
  signal?: AbortSignal,
) {
  const url = `/api/v2/storage/novel/${novelId}/chapters/stream`;
  return fetch(url, { signal }).then(async (res) => {
    if (!res.ok || !res.body) { onError(); return; }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let sawDone = false;
    while (true) {
      const { done, value } = await reader.read();
      buf += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const payload = line.slice(6);
          if (payload === "[DONE]") { sawDone = true; onDone(); return; }
          try { onChapter(JSON.parse(payload) as ChapterBrief); } catch {}
        }
      }
      if (done) {
        // 后端正常流以 data: [DONE] 收尾；未收到 [DONE] 就 EOF 视为异常终止
        if (sawDone) onDone(); else onError();
        return;
      }
    }
  }).catch((e: Error) => {
    // 网络/读取错误（非主动取消）→ 异常终止
    if (e.name !== "AbortError") onError();
  });
}

// ── Download ───────────────────────────────────────

export function searchDownload(params: {
  platform: string; query: string; mode?: string; variant?: string;
}) {
  const qs = new URLSearchParams({ query: params.query, platform: params.platform });
  if (params.mode) qs.set("mode", params.mode);
  if (params.variant) qs.set("variant", params.variant);
  return apiGet<SearchResult[]>(`/download/search?${qs}`);
}

export function fetchMeta(url: string, mode?: string, variant?: string, signal?: AbortSignal) {
  const qs = new URLSearchParams();
  if (mode) qs.set("mode", mode);
  if (variant) qs.set("variant", variant);
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiPost<NovelMeta>(`/download/novel${suffix}`, { url }, signal);
}

export function fetchChapterList(
  novelId: string, url: string, mode?: string, variant?: string, signal?: AbortSignal,
) {
  const qs = new URLSearchParams({ url });
  if (mode) qs.set("mode", mode);
  if (variant) qs.set("variant", variant);
  return apiGet<ChapterBrief[]>(`/download/novel/${novelId}/chapters?${qs}`, signal);
}

export function downloadChapters(
  novelId: string,
  chapters: { id: string; url: string; novel_id: string; title: string; order: number; volume: string | null }[],
  title: string,
  mode?: string,
  variant?: string,
  novelUrl?: string,
  platform?: string,
) {
  const qs = new URLSearchParams({ title });
  if (mode) qs.set("mode", mode);
  if (variant) qs.set("variant", variant);
  if (novelUrl) qs.set("novel_url", novelUrl);
  if (platform) qs.set("platform", platform);
  return apiPost<{ task_id: string; total: number }>(`/download/novel/${novelId}/chapter?${qs}`, chapters);
}

export function listTasks() {
  return apiGet<TaskInfo[]>("/download/tasks");
}

export function pauseTask(taskId: string) {
  return apiPost<void>(`/download/task/${taskId}/pause`, {});
}

export function resumeTask(taskId: string) {
  return apiPost<void>(`/download/task/${taskId}/resume`, {});
}

export function deleteTask(taskId: string) {
  return apiDelete(`/download/task/${taskId}`);
}

export function downloadPlatforms() {
  return apiGet<{ id: string; label: string }[]>("/download/platform");
}

export type SourceCapabilities = Record<string, Record<string, string[]>>;

export function fetchSources() {
  return apiGet<Record<string, { hosts: string[]; show_name: string; capabilities: Record<string, Record<string, string[]>> }>>("/download/sources");
}

// ── Config ─────────────────────────────────────────

export function getGlobalConfig() {
  return apiGet<GlobalConfig>("/config");
}

export function saveGlobalConfig(data: Partial<GlobalConfig>) {
  return apiPut<void>("/config", data);
}

export function getGroups() {
  return apiGet<GroupsConfig>("/config/groups");
}

export function saveGroups(data: GroupsConfig) {
  return apiPut<void>("/config/groups", data);
}

export function getFavorites() {
  return apiGet<{ favorites: string[] }>("/config/favorites");
}

export function addFavorite(novelId: string) {
  return apiPost<{ ok: boolean }>(`/config/favorites/${novelId}`, {});
}

export function removeFavorite(novelId: string) {
  return apiDelete(`/config/favorites/${novelId}`);
}

// ── Search History ─────────────────────────────────

export interface SearchHistoryItem {
  id: number; platform: string; mode: string; variant: string; keyword: string; searched_at: string;
}

export interface SearchHistoryGroup {
  date_label: string; items: SearchHistoryItem[];
}

export function getSearchHistory() {
  return apiGet<{ history: SearchHistoryGroup[] }>("/history/search");
}

export function addSearchHistory(platform: string, keyword: string, mode: string, variant: string) {
  return apiPost<{ status: string }>("/history/search", { platform, keyword, mode, variant });
}

export function deleteSearchHistory(historyId: number) {
  return apiDelete(`/history/search/${historyId}`);
}

export function getSiteConfig(website: string) {
  return apiGet<SiteConfig>(`/config/sites/${website}`);
}

export function saveSiteConfig(website: string, data: Partial<SiteConfig>) {
  return apiPut<void>(`/config/sites/${website}`, data);
}

export function getFormatConfig(format: string) {
  return apiGet<Record<string, unknown>>(`/config/formats/${format}`);
}

export function saveFormatConfig(format: string, data: Record<string, unknown>) {
  return apiPut<void>(`/config/formats/${format}`, data);
}

// ── Export ─────────────────────────────────────────

export function triggerExport(body: unknown) {
  return apiPost<{ task_id: string }>("/export", body);
}

export function exportTaskStatus(taskId: string) {
  return apiGet<ExportTaskResult>(`/export/task/${taskId}`);
}

// ── Helpers ────────────────────────────────────────

export function coverToUrl(cover: NovelMeta["cover"]): string | null {
  if (!cover) return null;
  if (cover.raw_data) {
    const fmt = cover.format ?? "jpeg";
    const mime = fmt === "png" ? "image/png" : fmt === "webp" ? "image/webp" : "image/jpeg";
    return `data:${mime};base64,${cover.raw_data}`;
  }
  if (cover.url) return cover.url;
  return null;
}
