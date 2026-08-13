/** 会话级缓存 — 所有值在浏览器刷新时清除，页面导航间保持。 */
const KEYS = {
  mode: "nd:mode",
  variant: "nd:variant",
  query: "nd:search:query",
  platform: "nd:search:platform",
  searchMode: "nd:search:mode",
  searchVariant: "nd:search:variant",
} as const;

export const SessionCache = {
  getMode(): string {
    return sessionStorage.getItem(KEYS.mode) ?? "browser";
  },
  setMode(mode: string): void {
    sessionStorage.setItem(KEYS.mode, mode);
  },
  getVariant(): string | undefined {
    return sessionStorage.getItem(KEYS.variant) ?? undefined;
  },
  setVariant(variant?: string): void {
    if (variant) sessionStorage.setItem(KEYS.variant, variant);
    else sessionStorage.removeItem(KEYS.variant);
  },
  /** 缓存最近一次搜索参数，页面切换后恢复。 */
  saveSearch(query: string, platform: string, mode?: string, variant?: string): void {
    sessionStorage.setItem(KEYS.query, query);
    sessionStorage.setItem(KEYS.platform, platform);
    if (mode) sessionStorage.setItem(KEYS.searchMode, mode);
    if (variant) sessionStorage.setItem(KEYS.searchVariant, variant);
  },
  getSearchQuery(): string {
    return sessionStorage.getItem(KEYS.query) ?? "";
  },
  getSearchPlatform(): string {
    return sessionStorage.getItem(KEYS.platform) ?? "fanqie";
  },
  getSearchMode(): string | undefined {
    return sessionStorage.getItem(KEYS.searchMode) ?? undefined;
  },
  getSearchVariant(): string | undefined {
    return sessionStorage.getItem(KEYS.searchVariant) ?? undefined;
  },
  getSearchParams(): { platform: string; query: string; mode?: string; variant?: string } | null {
    const query = this.getSearchQuery();
    if (!query) return null;
    return {
      query,
      platform: this.getSearchPlatform(),
      mode: this.getSearchMode(),
      variant: this.getSearchVariant(),
    };
  },
  clearSearch(): void {
    sessionStorage.removeItem(KEYS.query);
    sessionStorage.removeItem(KEYS.platform);
    sessionStorage.removeItem(KEYS.searchMode);
    sessionStorage.removeItem(KEYS.searchVariant);
  },
};
