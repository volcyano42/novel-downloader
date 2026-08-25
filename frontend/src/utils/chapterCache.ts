/** 章节列表缓存 — 用 sessionStorage 保留“content/time”之外的章节元数据。 */

import type {ChapterBrief} from "@/api/endpoints";

const PREFIX = "chaptersCache:";

interface CacheEntry {
  data: ChapterBrief[];
  ts: number;
}

export function getCachedChapters(novelId: string): ChapterBrief[] | null {
  try {
    const raw = sessionStorage.getItem(PREFIX + novelId);
    if (!raw) return null;
    const entry = JSON.parse(raw) as CacheEntry;
    return entry.data ?? null;
  } catch {
    return null;
  }
}

export function setCachedChapters(novelId: string, data: ChapterBrief[]) {
  try {
    const entry: CacheEntry = { data, ts: Date.now() };
    sessionStorage.setItem(PREFIX + novelId, JSON.stringify(entry));
  } catch {
    // sessionStorage 满了就静默跳过
  }
}

export function clearCachedChapters(novelId: string) {
  sessionStorage.removeItem(PREFIX + novelId);
}
