/** 会话级缓存 — 所有值在浏览器刷新时清除，页面导航间保持。 */
const KEYS = {
  mode: "nd:mode",
  provider: "nd:provider",
  query: "nd:search:query",
  platform: "nd:search:platform",
  searchMode: "nd:search:mode",
  searchProvider: "nd:search:provider",
} as const;

export const SessionCache = {
  getMode(): string {
    return sessionStorage.getItem(KEYS.mode) ?? "browser";
  },
  setMode(mode: string): void {
    sessionStorage.setItem(KEYS.mode, mode);
  },
  getProvider(): string | undefined {
    return sessionStorage.getItem(KEYS.provider) ?? undefined;
  },
  setProvider(provider?: string): void {
    if (provider) sessionStorage.setItem(KEYS.provider, provider);
    else sessionStorage.removeItem(KEYS.provider);
  },
  /** 缓存最近一次搜索参数，页面切换后恢复。 */
  saveSearch(query: string, platform: string, mode?: string, provider?: string): void {
    sessionStorage.setItem(KEYS.query, query);
    sessionStorage.setItem(KEYS.platform, platform);
    if (mode) sessionStorage.setItem(KEYS.searchMode, mode);
    if (provider) sessionStorage.setItem(KEYS.searchProvider, provider);
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
  getSearchProvider(): string | undefined {
    return sessionStorage.getItem(KEYS.searchProvider) ?? undefined;
  },
  getSearchParams(): { platform: string; query: string; mode?: string; provider?: string } | null {
    const query = this.getSearchQuery();
    if (!query) return null;
    return {
      query,
      platform: this.getSearchPlatform(),
      mode: this.getSearchMode(),
      provider: this.getSearchProvider(),
    };
  },
  clearSearch(): void {
    sessionStorage.removeItem(KEYS.query);
    sessionStorage.removeItem(KEYS.platform);
    sessionStorage.removeItem(KEYS.searchMode);
    sessionStorage.removeItem(KEYS.searchProvider);
  },
};
