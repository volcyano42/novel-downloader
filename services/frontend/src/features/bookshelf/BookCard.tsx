import { useState, useCallback } from "react";
import { BookOpen, Download, FileDown, MoreHorizontal, Loader2, Trash2, FolderPlus, Folder } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDeleteNovel, useExport, useSaveConfig, useConfig } from "@/hooks/index";
import { ExportDialog } from "@/features/download/ExportDialog";
import { DownloadDialog } from "@/features/download/DownloadDialog";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface BookCardProps {
  title: string; author: string; novelId?: string; cover?: string | null; progress?: number;
  onRead?: () => void; className?: string;
  groups?: string[];
  currentGroup?: string;
  onDelete?: (novelId: string) => void;
  onDownloadAll?: (novelId: string, mode: string, provider?: string) => void;
  serial?: number;
  defaultMode?: string;
  defaultProvider?: string;
}

export function BookCard({ title, author, novelId, cover, progress = 0, onRead, className, groups = [], currentGroup, onDelete, onDownloadAll, serial, defaultMode, defaultProvider }: BookCardProps) {
  const [showExport, setShowExport] = useState(false);
  const [showDownloadDialog, setShowDownloadDialog] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [inlineNewGroup, setInlineNewGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const exportMut = useExport();
  const { data: config } = useConfig();
  const saveConfigMut = useSaveConfig();

  const saveGroups = useCallback(async (newGroups: Record<string, Record<string, object>>) => {
    if (!config) return;
    await saveConfigMut.mutateAsync({ ...config, groups: newGroups } as unknown as Record<string, unknown>);
  }, [config, saveConfigMut]);

  const handleMoveToGroup = useCallback((novelId: string, group: string) => {
    if (!config) return;
    const newGroups = { ...config.groups };
    for (const g of Object.keys(newGroups)) {
      if (novelId in newGroups[g]) {
        const { [novelId]: _, ...rest } = newGroups[g];
        if (Object.keys(rest).length === 0) delete newGroups[g];
        else newGroups[g] = rest;
        break;
      }
    }
    newGroups[group] = { ...newGroups[group], [novelId]: {} };
    saveGroups(newGroups);
  }, [config, saveGroups]);

  const handleRemoveFromGroup = useCallback((novelId: string) => {
    if (!config) return;
    const newGroups = { ...config.groups };
    for (const g of Object.keys(newGroups)) {
      if (novelId in newGroups[g]) {
        const { [novelId]: _, ...rest } = newGroups[g];
        if (Object.keys(rest).length === 0) delete newGroups[g];
        else newGroups[g] = rest;
        break;
      }
    }
    saveGroups(newGroups);
  }, [config, saveGroups]);

  const handleNewGroup = useCallback((novelId: string, name: string) => {
    handleMoveToGroup(novelId, name);
  }, [handleMoveToGroup]);

  const handleExportClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setShowExport(true);
  }, []);

  const handleStartExport = useCallback(async (formats: string[]) => {
    if (!novelId || exporting) return;
    setExporting(true);
    try {
      const body: Record<string, unknown> = { novel_id: novelId, chapter_id: null };
      if (config) {
        if (formats.includes("txt")) body.txt = { ...config.txt, enabled: true };
        if (formats.includes("epub")) body.epub = { ...config.epub, enabled: true };
        if (formats.includes("img")) body.img = { ...config.img, enabled: true };
      }
      const task = await exportMut.mutateAsync(body);
      if (task.status === "completed" && task.task_id) {
        const a = document.createElement("a");
        a.href = `/api/v2/export/download/${task.task_id}`;
        a.download = "";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
    } catch { /* Toast handled by mutation */ }
    finally { setExporting(false); setShowExport(false); }
  }, [novelId, exporting, config, exportMut]);

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
        <div className="aspect-[4/5] overflow-hidden rounded-t-2xl bg-slate-100 p-[25%] relative">
          {cover ? (
            <img src={cover} alt={title} className="h-full w-full object-contain animate-in fade-in duration-300" loading="lazy" width="200" height="300" />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <BookOpen className="h-10 w-10 text-slate-300" strokeWidth={1.5} />
            </div>
          )}
          <div className="absolute bottom-1.5 right-1.5 flex items-center gap-0.5 opacity-0 group-hover/card:opacity-100 transition-opacity duration-200">
            <button onClick={e => { e.stopPropagation(); setShowDownloadDialog(true); }}
              className="rounded-lg bg-white/80 p-1.5 text-slate-400 hover:text-indigo-500 hover:bg-white transition-colors shadow-sm">
              <Download className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
            <button onClick={handleExportClick}
              className="rounded-lg bg-white/80 p-1.5 text-slate-400 hover:text-indigo-500 hover:bg-white transition-colors shadow-sm">
              {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} /> : <FileDown className="h-3.5 w-3.5" strokeWidth={2} />}
            </button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button onClick={e => e.stopPropagation()}
                  className="rounded-lg bg-white/80 p-1.5 text-slate-400 hover:text-indigo-500 hover:bg-white transition-colors shadow-sm">
                  <MoreHorizontal className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent onClick={e => e.stopPropagation()} align="end" className="w-40 !max-h-none !overflow-y-visible rounded-xl border-white/20 bg-white/95 backdrop-blur-xl shadow-xl py-1.5">
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
          <p className="text-sm text-slate-500">{author}</p>
          {progress > 0 && <div className="mt-auto pt-2"><div className="h-1.5 rounded-full bg-slate-200"><div className="h-full rounded-full bg-indigo-500 transition-all duration-500" style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} /></div></div>}
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
      <DownloadDialog open={showDownloadDialog} onClose={() => setShowDownloadDialog(false)}
        novelTitle={title} chapterCount={serial ?? 0} variant="download"
        initialMode={defaultMode} initialProvider={defaultProvider}
        onStart={(mode, provider) => { setShowDownloadDialog(false); onDownloadAll?.(novelId!, mode, provider); }}
      />
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
