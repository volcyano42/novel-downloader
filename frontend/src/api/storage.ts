import { apiGet, apiDelete } from "./client";

export interface NovelMeta {
  title: string; url: string; id: string; serial: number; author: string; description: string;
  tags: string[] | null; count: number | null;
  cover: { raw_data: string | null; alt: string | null; url: string | null; format: string | null } | null;
}

export interface ChapterBrief {
  id: string; url: string; index_url: string; title: string; order: number;
  volume: string | null; count: number | null; is_complete: boolean;
}

export interface ChapterData extends ChapterBrief {
  content: string | null; time: number | null;
  images: { raw_data: string | null; alt: string | null; insert: number | null; url: string | null }[];
}

export const storageApi = {
  listNovels: () => apiGet<NovelMeta[]>("/storage/novel"),
  getMeta: (novelId: string) => apiGet<NovelMeta>(`/storage/novel/${novelId}/meta`),
  deleteNovel: (novelId: string) => apiDelete(`/storage/novel/${novelId}`),
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
