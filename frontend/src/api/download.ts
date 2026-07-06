import { apiGet, apiPost } from "./client";
import type { ChapterBrief } from "./storage";

export interface SearchResult { title: string; author: string; url: string; description: string | null; }
export interface Platform { id: string; label: string; }

export const downloadApi = {
  search: (params: { platform: string; query: string; page?: number; mode?: string; engine_id?: string }) => {
    const qs = new URLSearchParams(); qs.set("query", params.query);
    qs.set("platform", params.platform);
    if (params.page) qs.set("page", String(params.page));
    if (params.mode) qs.set("mode", params.mode);
    qs.set("engine_id", params.engine_id ?? "default");
    return apiGet<SearchResult[]>(`/download/search?${qs}`);
  },
  fetchMeta: (url: string, engineId = "default") => apiPost<any>("/download/novel", { url, engine_id: engineId }),
  fetchChapterList: (novelId: string, url: string, engineId = "default") => apiGet<ChapterBrief[]>(`/download/novel/${novelId}/chapters?url=${encodeURIComponent(url)}&engine_id=${engineId}`),
  downloadChapters: (novelId: string, chapters: { id: string; url: string; index_url: string; title: string; order: number; volume: string | null }[], engineId = "default") =>
    apiPost<any>(`/download/novel/${novelId}/chapter?engine_id=${engineId}`, chapters),
  platforms: () => apiGet<Platform[]>("/download/platform"),
};
