/** React Query hooks — 所有数据获取和变更操作 */

import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import type {ChapterBrief} from "@/api/endpoints";
import {
  addFavorite,
  addSearchHistory,
  deleteNovel,
  deleteSearchHistory,
  deleteTask,
  downloadChapters,
  downloadPlatforms,
  exportTaskStatus,
  fetchChapterList,
  fetchMeta,
  fetchSources,
  getChapter,
  getFavorites,
  getFormatConfig,
  getGlobalConfig,
  getGroups,
  getMeta,
  getSearchHistory,
  getSiteConfig,
  listChapters,
  listNovels,
  listTasks,
  pauseTask,
  removeFavorite,
  resumeTask,
  saveFormatConfig,
  saveGlobalConfig,
  saveGroups,
  saveSiteConfig,
  searchDownload,
  triggerExport,
} from "@/api/endpoints";

// ── Queries ────────────────────────────────────────

export function useNovels() {
  return useQuery({
    queryKey: ["novels"],
    queryFn: () => listNovels(),
    staleTime: Infinity,
  });
}

export function useNovelMeta(novelId: string | undefined) {
  return useQuery({
    queryKey: ["novel-meta", novelId],
    queryFn: () => getMeta(novelId!),
    enabled: !!novelId,
    staleTime: 60_000,
  });
}

export function useChapters(novelId: string | undefined) {
  return useQuery({
    queryKey: ["chapters", novelId],
    queryFn: () => listChapters(novelId!, { size: 20000 }),
    enabled: !!novelId,
    staleTime: 30_000,
  });
}

export function useChapter(novelId: string | undefined, chapterId: string | undefined) {
  return useQuery({
    queryKey: ["chapter", novelId, chapterId],
    queryFn: () => getChapter(novelId!, chapterId!),
    enabled: !!novelId && !!chapterId,
  });
}

export function useGlobalConfig() {
  return useQuery({
    queryKey: ["global-config"],
    queryFn: () => getGlobalConfig(),
    staleTime: Infinity,
  });
}

export function useGroups() {
  return useQuery({
    queryKey: ["groups"],
    queryFn: () => getGroups(),
    staleTime: Infinity,
  });
}

export function useSiteConfig(website: string | undefined) {
  return useQuery({
    queryKey: ["site-config", website],
    queryFn: () => getSiteConfig(website!),
    enabled: !!website,
    staleTime: Infinity,
  });
}

export function useFormatConfig(format: string | undefined) {
  return useQuery({
    queryKey: ["format-config", format],
    queryFn: () => getFormatConfig(format!),
    enabled: !!format,
    staleTime: Infinity,
  });
}

export function usePlatforms() {
  return useQuery({
    queryKey: ["platforms"],
    queryFn: downloadPlatforms,
    staleTime: Infinity,
  });
}

export function useSources() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: fetchSources,
    staleTime: Infinity,
  });
}

export function useTasks(enabled: boolean) {
  return useQuery({
    queryKey: ["tasks"],
    queryFn: listTasks,
    enabled,
    refetchInterval: enabled ? 1000 : false,
  });
}

export function useSearch(params: {
  platform: string; query: string; mode?: string; variant?: string;
} | null) {
  return useQuery({
    queryKey: ["search", params],
    queryFn: () => searchDownload(params!),
    enabled: !!params && params.query.trim().length > 0,
    staleTime: 30_000,
    // 搜索是用户主动的一次性操作，失败不自动重试（避免重复请求）
    retry: 0,
  });
}

export function useRemoteChapters(
  novelId: string | undefined,
  url: string | undefined,
  mode?: string,
  variant?: string,
) {
  return useQuery({
    queryKey: ["remote-chapters", novelId, url, mode, variant],
    queryFn: () => fetchChapterList(novelId!, url!, mode, variant),
    enabled: !!novelId && !!url,
    staleTime: 30_000,
  });
}

// ── Mutations ──────────────────────────────────────

export function useDeleteNovel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteNovel,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["novels"] }),
  });
}

export function useSaveGlobalConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: saveGlobalConfig,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["global-config"] }),
  });
}

export function useSaveGroups() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: saveGroups,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["groups"] }),
  });
}

export function useFavorites() {
  return useQuery({
    queryKey: ["favorites"],
    queryFn: () => getFavorites().then(r => r.favorites),
    staleTime: Infinity,
  });
}

export function useToggleFavorite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ novelId, favorited }: { novelId: string; favorited: boolean }) =>
      favorited ? addFavorite(novelId) : removeFavorite(novelId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  });
}

// ── Search History ────────────────────────────────

export function useSearchHistory() {
  return useQuery({
    queryKey: ["search-history"],
    queryFn: () => getSearchHistory().then(r => r.history),
  });
}

export function useAddSearchHistory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ platform, keyword, mode, variant }: { platform: string; keyword: string; mode?: string; variant?: string }) =>
      addSearchHistory(platform, keyword, mode ?? "", variant ?? ""),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["search-history"] }),
  });
}

export function useDeleteSearchHistory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (historyId: number) => deleteSearchHistory(historyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["search-history"] }),
  });
}

export function useSaveSiteConfig(website: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => saveSiteConfig(website, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-config", website] }),
  });
}

export function useSaveFormatConfig(format: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => saveFormatConfig(format, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["format-config", format] }),
  });
}

export function useDownloadMutation() {
  return useMutation({
    mutationFn: (args: {
      novelId: string;
      chapters: { id: string; url: string; novel_id: string; title: string; order: number; volume: string | null }[];
      title: string;
      mode?: string;
      variant?: string;
      novelUrl?: string;
      platform?: string;
    }) =>
      downloadChapters(args.novelId, args.chapters, args.title, args.mode, args.variant, args.novelUrl, args.platform),
  });
}

export function usePauseTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: pauseTask,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

export function useResumeTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: resumeTask,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteTask,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

export function useExport() {
  return useMutation({
    mutationFn: async (body: unknown) => {
      const { task_id } = await triggerExport(body);
      for (let i = 0; i < 120; i++) {
        await new Promise(r => setTimeout(r, 1000));
        const task = await exportTaskStatus(task_id);
        if (task.status === "completed" || task.status === "failed") return task;
      }
      throw new Error("导出超时");
    },
  });
}

export function useFetchMeta() {
  return useMutation({
    mutationFn: (args: { url: string; mode?: string; variant?: string }) =>
      fetchMeta(args.url, args.mode, args.variant),
  });
}

// ── Helpers ────────────────────────────────────────

export function compareChapters(remote: ChapterBrief[], local: ChapterBrief[]) {
  const localMap = new Map(local.map(c => [c.id, c]));
  return remote.map(r => ({
    remote: r,
    local: localMap.get(r.id) ?? null,
  }));
}

// ── Backward compat aliases ────────────────────────


