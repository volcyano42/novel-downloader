import { apiGet, apiDelete } from "./client";

export interface NovelMeta {
  title: string; url: string; id: string; serial: number; author: string; description: string;
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

// ── localStorage 缓存 ──
const LS_NOVELS = "nl_novels";
const LS_COVER_PREFIX = "nl_cover_";

function _cacheGet<T>(key: string): T | null {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) as T : null; }
  catch { return null; }
}
function _cacheSet(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}
function _cacheRemove(pattern?: string) {
  try {
    const keys = Object.keys(localStorage);
    for (const k of keys) {
      if (!pattern || k.startsWith(pattern)) localStorage.removeItem(k);
    }
  } catch {}
}

export const storageApi = {
  listNovels: async () => {
    const cached = _cacheGet<NovelMeta[]>(LS_NOVELS);
    if (cached) return cached;
    const data = await apiGet<NovelMeta[]>("/storage/novel");
    _cacheSet(LS_NOVELS, data);
    return data;
  },
  refreshNovels: async () => {
    const data = await apiGet<NovelMeta[]>("/storage/novel");
    _cacheSet(LS_NOVELS, data);
    return data;
  },
  getMeta: (novelId: string) => apiGet<NovelMeta>(`/storage/novel/${novelId}/meta`),
  getCover: async (novelId: string): Promise<string | null> => {
    const key = LS_COVER_PREFIX + novelId;
    const cachedUrl = _cacheGet<string>(key);
    if (cachedUrl) return cachedUrl;
    const cover = await apiGet<NovelMeta["cover"]>(`/storage/novel/${novelId}/cover`);
    const url = coverToUrl(cover);
    if (url) _cacheSet(key, url);
    return url;
  },
  deleteNovel: (novelId: string) => {
    _cacheRemove(LS_COVER_PREFIX + novelId);
    // 也从小说列表中移除
    const novels = _cacheGet<NovelMeta[]>(LS_NOVELS);
    if (novels) {
      _cacheSet(LS_NOVELS, novels.filter(n => n.id !== novelId));
    }
    return apiDelete(`/storage/novel/${novelId}`);
  },
  listChapters: (novelId: string, params?: { order?: string; page?: number; size?: number }) => {
    const qs = new URLSearchParams();
    if (params?.order) qs.set("order", params.order);
    if (params?.page) qs.set("page", String(params.page));
    if (params?.size) qs.set("size", String(params.size));
    return apiGet<ChapterBrief[]>(`/storage/novel/${novelId}/chapters${qs.toString() ? `?${qs}` : ""}`);
  },
  getChapter: (novelId: string, chapterId: string) => apiGet<ChapterData>(`/storage/novel/${novelId}/chapter/${chapterId}`),
};

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
