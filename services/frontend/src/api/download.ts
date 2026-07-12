import { apiGet, apiPost, apiDelete } from "./client";
import type { ChapterBrief } from "./storage";

export interface SearchResult { title: string; author: string; url: string; description: string | null; }
export interface Platform { id: string; label: string; }
export interface TaskInfo {
  task_id: string; novel_id: string; title: string; total: number;
  progress: number; status: string; error: string | null; errors: string[];
  current_title: string;
}

export const downloadApi = {
  search: (params: { platform: string; query: string; page?: number; mode?: string; provider?: string }) => {
    const qs = new URLSearchParams(); qs.set("query", params.query);
    qs.set("platform", params.platform);
    if (params.page) qs.set("page", String(params.page));
    if (params.mode) qs.set("mode", params.mode);
    if (params.provider) qs.set("provider", params.provider);
    return apiGet<SearchResult[]>(`/download/search?${qs}`);
  },
  fetchMeta: (url: string, mode?: string, provider?: string, signal?: AbortSignal) => {
    const qs = new URLSearchParams();
    if (mode) qs.set("mode", mode);
    if (provider) qs.set("provider", provider);
    const suffix = qs.toString() ? `?${qs}` : "";
    return apiPost<any>(`/download/novel${suffix}`, { url }, signal);
  },
  fetchChapterList: (novelId: string, url: string, mode?: string, provider?: string, signal?: AbortSignal) => {
    const qs = new URLSearchParams(); qs.set("url", url);
    if (mode) qs.set("mode", mode);
    if (provider) qs.set("provider", provider);
    return apiGet<ChapterBrief[]>(`/download/novel/${novelId}/chapters?${qs}`, signal);
  },
  downloadChapters: (novelId: string, chapters: { id: string; url: string; novel_id: string; title: string; order: number; volume: string | null }[], title: string, mode?: string, provider?: string, novelUrl?: string, platform?: string) => {
    const qs = new URLSearchParams(); qs.set("title", title);
    if (mode) qs.set("mode", mode);
    if (provider) qs.set("provider", provider);
    if (novelUrl) qs.set("novel_url", novelUrl);
    if (platform) qs.set("platform", platform);
    return apiPost<{ task_id: string; total: number }>(`/download/novel/${novelId}/chapter?${qs}`, chapters);
  },
  listTasks: () => apiGet<TaskInfo[]>("/download/tasks"),
  pauseTask: (taskId: string) => apiPost<any>(`/download/task/${taskId}/pause`, {}),
  resumeTask: (taskId: string) => apiPost<any>(`/download/task/${taskId}/resume`, {}),
  deleteTask: (taskId: string) => apiDelete(`/download/task/${taskId}`),
  platforms: () => apiGet<Platform[]>("/download/platform"),
};
