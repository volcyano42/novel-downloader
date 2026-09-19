import {useCallback, useState} from "react";
import {BookOpen, FileDown, Folder, FolderPlus, Heart, MoreHorizontal, Trash2} from "lucide-react";
import {cn} from "@/lib/utils";
import {useExport, useFavorites, useGroups, useSaveGroups, useToggleFavorite} from "@/hooks/index";
import {ExportDialog} from "@/features/download/ExportDialog";
import {useToast} from "@/components/toast-context";
import {Tooltip, TooltipContent, TooltipProvider, TooltipTrigger} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface BookCardProps {
  title: string; author: string; novelId?: string; cover?: string | null;
  onRead?: () => void; className?: string;
  groups?: string[];
  currentGroup?: string;
  onDelete?: (novelId: string) => void;
}

export function BookCard({ title, novelId, cover, onRead, className, groups = [], currentGroup, onDelete }: BookCardProps) {
  const [showExport, setShowExport] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [inlineNewGroup, setInlineNewGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const exportMut = useExport();
  const toast = useToast();
  const { data: groupsData = {} } = useGroups();
  const saveGroupsMut = useSaveGroups();
  const { data: favorites = [] } = useFavorites();
  const toggleFavMut = useToggleFavorite();

  const saveGroupsFn = useCallback(async (newGroups: Record<string, Record<string, object>>) => {
    await saveGroupsMut.mutateAsync(newGroups);
  }, [saveGroupsMut]);

  const handleMoveToGroup = useCallback((novelId: string, group: string) => {
    const newGroups = { ...groupsData };
    for (const g of Object.keys(newGroups)) {
      if (novelId in newGroups[g]) {
        const { [novelId]: _, ...rest } = newGroups[g];
        if (Object.keys(rest).length === 0) delete newGroups[g];
        else newGroups[g] = rest;
        break;
      }
    }
    newGroups[group] = { ...newGroups[group], [novelId]: { pending_export: false } };
    saveGroupsFn(newGroups);
  }, [groupsData, saveGroupsFn]);

  const handleRemoveFromGroup = useCallback((novelId: string) => {
    const newGroups = { ...groupsData };
    for (const g of Object.keys(newGroups)) {
      if (novelId in newGroups[g]) {
        const { [novelId]: _, ...rest } = newGroups[g];
        if (Object.keys(rest).length === 0) delete newGroups[g];
        else newGroups[g] = rest;
        break;
      }
    }
    saveGroupsFn(newGroups);
  }, [groupsData, saveGroupsFn]);

  const handleNewGroup = useCallback((novelId: string, name: string) => {
    handleMoveToGroup(novelId, name);
  }, [handleMoveToGroup]);

  const handleStartExport = useCallback(async (formats: string[]) => {
    if (!novelId || exporting) return;
    setExporting(true);
    try {
      const body: Record<string, unknown> = { novel_id: novelId, chapter_id: null };
      if (formats.includes("txt")) body.txt = { enabled: true };
      if (formats.includes("epub")) body.epub = { enabled: true };
      if (formats.includes("img")) body.img = { enabled: true };
      const task = await exportMut.mutateAsync(body);
      if (task.status === "completed" && task.task_id) {
        toast("导出成功，正在下载…", "success");
        const androidBridge = (window as unknown as {
          AndroidBridge?: { saveExport(taskId: string, fileName: string): void };
        }).AndroidBridge;
        if (androidBridge) {
          // Android APK：走系统"保存到"对话框（SAF）；文件名清洗非法字符
          const safeTitle = title.replace(/[\\/:*?"<>|]/g, "_");
          androidBridge.saveExport(task.task_id, `${safeTitle}.zip`);
        } else {
          // 桌面/浏览器：现有逻辑
          window.open(`/api/v2/export/download/${task.task_id}`, "_self");
        }
      } else {
        toast(`导出失败：${task.error || "未知错误"}`, "error");
      }
    } catch (e: unknown) {
      toast(`导出失败：${(e as Error).message || "网络错误"}`, "error");
    }
    finally { setExporting(false); setShowExport(false); }
  }, [novelId, exporting, exportMut, toast, title]);

  const handleDelete = useCallback(() => {
    if (!novelId) return;
    onDelete?.(novelId);
    setShowDeleteConfirm(false);
  }, [novelId, onDelete]);

  const handleNewGroupSubmit = useCallback(() => {
    const name = newGroupName.trim();
    if (!name || !novelId) return;
    handleNewGroup(novelId, name);
    setInlineNewGroup(false);
    setNewGroupName("");
  }, [novelId, newGroupName, handleNewGroup]);

  return (
    <>
      <div className={cn("group/card cursor-pointer flex flex-col rounded-2xl border border-white/20 bg-white/80 backdrop-blur-xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-[0_20px_40px_rgb(0,0,0,0.06)] hover:-translate-y-0.5 transition-all duration-300 ease-out", className)}
        onClick={onRead}>
        <div className="aspect-[4/5] overflow-hidden rounded-t-2xl bg-slate-100 p-[20%] relative">
          {cover ? (
            <img src={cover} alt={title} className="h-full w-full object-contain animate-in fade-in duration-300" loading="lazy" width="200" height="300" />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <BookOpen className="h-10 w-10 text-slate-300" strokeWidth={1.5} />
            </div>
          )}
          {novelId && (
            <div className="absolute bottom-1.5 right-1.5 md:opacity-0 md:group-hover/card:opacity-100 transition-opacity duration-200">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button onClick={e => e.stopPropagation()}
                  className="rounded-lg bg-white/80 p-1.5 text-slate-400 hover:text-indigo-500 hover:bg-white transition-colors shadow-sm">
                  <MoreHorizontal className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent onClick={e => e.stopPropagation()} align="end" className="w-40 !max-h-none !overflow-y-visible rounded-xl border-white/20 bg-white/95 backdrop-blur-xl shadow-xl py-1.5">
                {novelId && (
                  <DropdownMenuItem onSelect={() => toggleFavMut.mutate({ novelId, favorited: !favorites.includes(novelId) })}
                    className="rounded-lg">
                    <Heart className={`mr-2 h-3.5 w-3.5 ${favorites.includes(novelId) ? "text-rose-500" : ""}`}
                      fill={favorites.includes(novelId) ? "currentColor" : "none"} strokeWidth={2} />
                    {favorites.includes(novelId) ? "取消收藏" : "收藏"}
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => setShowExport(true)}
                  className="rounded-lg">
                  <FileDown className="mr-2 h-3.5 w-3.5" />
                  导出
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger className="rounded-lg">
                    <FolderPlus className="mr-2 h-3.5 w-3.5" />
                    分组
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent className="w-36 rounded-xl border-white/20 bg-white/95 backdrop-blur-xl shadow-xl py-1.5">
                    {groups.filter(g => g !== currentGroup).map(g => (
                      <DropdownMenuItem key={g} onSelect={() => handleMoveToGroup(novelId!, g)}
                        className="rounded-lg">
                        <Folder className="mr-2 h-3.5 w-3.5 text-slate-400" />
                        {g}
                      </DropdownMenuItem>
                    ))}
                    {groups.filter(g => g !== currentGroup).length > 0 && <DropdownMenuSeparator />}
                    {currentGroup && (
                      <DropdownMenuItem onSelect={() => handleRemoveFromGroup(novelId!)}
                        className="text-slate-500 focus:text-slate-700 rounded-lg">
                        <FolderPlus className="mr-2 h-3.5 w-3.5 text-slate-400" />
                        移除分组
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuSeparator />
                    {inlineNewGroup ? (
                      <div className="px-2 py-1">
                        <input value={newGroupName}
                          onChange={e => setNewGroupName(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === "Enter") handleNewGroupSubmit();
                            if (e.key === "Escape") { setInlineNewGroup(false); setNewGroupName(""); }
                            e.stopPropagation();
                          }}
                          onBlur={() => { setInlineNewGroup(false); setNewGroupName(""); }}
                          placeholder="输入分组名" autoFocus
                          className="w-full h-7 rounded-lg border border-slate-200 bg-white px-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400/30"
                        />
                      </div>
                    ) : (
                      <DropdownMenuItem onSelect={e => { e.preventDefault(); setInlineNewGroup(true); setNewGroupName(""); }}
                        className="text-indigo-500 focus:text-indigo-600 focus:bg-indigo-50 rounded-lg">
                        <FolderPlus className="mr-2 h-3.5 w-3.5 text-indigo-500" />
                        新建分组
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-red-500 focus:text-red-500 rounded-lg"
                  onClick={() => setTimeout(() => setShowDeleteConfirm(true), 100)}>
                  <Trash2 className="mr-2 h-3.5 w-3.5" />
                  删除
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          )}
        </div>
        <div className="flex flex-1 flex-col gap-1 px-4 py-3">
          {novelId && <p className="truncate text-[11px] text-slate-400 font-mono">{novelId}</p>}
          <TooltipProvider delayDuration={500}>
            <Tooltip>
              <TooltipTrigger asChild>
                <h3 className="truncate text-base font-semibold text-slate-800">{title}</h3>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-[280px] text-xs font-semibold">{title}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          {/* progress bar removed — always 0 */}
        </div>
      </div>

      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent className="max-w-sm rounded-2xl border border-white/20 bg-white/95 backdrop-blur-xl shadow-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              将删除《{title}》的书架记录及所有已下载的章节数据，此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-500 hover:bg-red-600">确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <ExportDialog open={showExport} onClose={() => setShowExport(false)} novelTitle={title} onExport={handleStartExport} />
    </>
  );
}

export function BookCardSkeleton() {
  return (
    <div className="flex flex-col rounded-2xl border border-white/20 bg-white/80">
      <div className="aspect-[4/5] animate-pulse rounded-t-2xl bg-slate-300/60" />
      <div className="flex flex-col gap-2 px-4 py-3">
        <div className="h-4 w-3/4 animate-pulse rounded bg-slate-300/60" />
        <div className="h-3 w-1/2 animate-pulse rounded bg-slate-300/60" />
      </div>
    </div>
  );
}
