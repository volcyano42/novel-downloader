/** 所有 API 端点 + 类型定义 — /api/v2 */

import { apiGet, apiPost, apiPut, apiDelete } from "./client";

// ── Types ──────────────────────────────────────────

export interface NovelMeta {
  title: string; url: string; id: string; serial: number;
  author: string; description: string;
  tags: string[] | null; count: number | null;
  cover: { raw_data: string | null; alt: string | null; url: string | null; format: string | null } | null;
}

export interface ChapterBrief {
  id: string; url: string; novel_id: string; title: string; order: number;
  volume: string | null; count: number | null; downloaded: boolean;
}

export interface ChapterData extends ChapterBrief {
  content: string | null; time: number | null;
  images: { raw_data: string | null; alt: string | null; insert: number | null; url: string | null }[];
}

export interface SearchResult {
  title: string; author: string; url: string; description: string | null;
}

export interface TaskInfo {
  task_id: string; novel_id: string; title: string; total: number;
  progress: number; status: string; error: string | null; errors: string[];
  current_title: string;
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
  name: string; mode: string; max_workers: number; log_level: string;
  notify: NotifyConfig;
}

export interface SiteConfig {
  browser: EngineOptions; requests: EngineOptions; api: EngineOptions;
  api_providers: string[];
}

export type GroupsConfig = Record<string, Record<string, object>>;

export interface ExportTaskResult {
  task_id: string; status: string; progress: number;
  formats?: string[]; path?: string | null;
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

// ── Download ───────────────────────────────────────

export function searchDownload(params: {
  platform: string; query: string; page?: number; mode?: string; provider?: string;
}) {
  const qs = new URLSearchParams({ query: params.query, platform: params.platform });
  if (params.page) qs.set("page", String(params.page));
  if (params.mode) qs.set("mode", params.mode);
  if (params.provider) qs.set("provider", params.provider);
  return apiGet<SearchResult[]>(`/download/search?${qs}`);
}

export function fetchMeta(url: string, mode?: string, provider?: string, signal?: AbortSignal) {
  const qs = new URLSearchParams();
  if (mode) qs.set("mode", mode);
  if (provider) qs.set("provider", provider);
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiPost<NovelMeta>(`/download/novel${suffix}`, { url }, signal);
}

export function fetchChapterList(
  novelId: string, url: string, mode?: string, provider?: string, signal?: AbortSignal,
) {
  const qs = new URLSearchParams({ url });
  if (mode) qs.set("mode", mode);
  if (provider) qs.set("provider", provider);
  return apiGet<ChapterBrief[]>(`/download/novel/${novelId}/chapters?${qs}`, signal);
}

export function downloadChapters(
  novelId: string,
  chapters: { id: string; url: string; novel_id: string; title: string; order: number; volume: string | null }[],
  title: string,
  mode?: string,
  provider?: string,
  novelUrl?: string,
  platform?: string,
) {
  const qs = new URLSearchParams({ title });
  if (mode) qs.set("mode", mode);
  if (provider) qs.set("provider", provider);
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

export function exportFormats() {
  return apiGet<{ id: string; label: string }[]>("/export/format");
}

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
