/** 会话级缓存 — 所有值在浏览器刷新时清除，页面导航间保持。 */
const KEYS = {
  query: "nd:search:query",
  source: "nd:search:source",
} as const;

export const SessionCache = {
  /** 缓存最近一次搜索参数，页面切换后恢复。 */
  saveSearch(query: string, source?: string): void {
    sessionStorage.setItem(KEYS.query, query);
    if (source) sessionStorage.setItem(KEYS.source, source);
    else sessionStorage.removeItem(KEYS.source);
  },
  getSearchQuery(): string {
    return sessionStorage.getItem(KEYS.query) ?? "";
  },
  /** 恢复最近一次搜索参数；source 为空表示「并发全部书源」。 */
  getSearchParams(): { source: string; query: string } | null {
    const query = this.getSearchQuery();
    if (!query) return null;
    return {
      query,
      source: sessionStorage.getItem(KEYS.source) ?? "",
    };
  },
  clearSearch(): void {
    sessionStorage.removeItem(KEYS.query);
    sessionStorage.removeItem(KEYS.source);
  },
};
