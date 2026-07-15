/** 会话级缓存 — 所有值在浏览器刷新时清除，页面导航间保持。 */
const KEYS = {
  mode: "nd:mode",
  provider: "nd:provider",
  query: "nd:search:query",
  platform: "nd:search:platform",
  results: "nd:search:results",
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
  saveSearch(query: string, platform: string): void {
    sessionStorage.setItem(KEYS.query, query);
    sessionStorage.setItem(KEYS.platform, platform);
  },
  getSearchQuery(): string {
    return sessionStorage.getItem(KEYS.query) ?? "";
  },
  getSearchPlatform(): string {
    return sessionStorage.getItem(KEYS.platform) ?? "fanqie";
  },
  clearSearch(): void {
    sessionStorage.removeItem(KEYS.query);
    sessionStorage.removeItem(KEYS.platform);
  },
};
