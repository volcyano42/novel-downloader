import { apiGet, apiPost } from "./client";

export interface ExportTaskResult {
  task_id: string; status: string; progress: number;
  formats?: string[]; path?: string | null;
}

export const exportApi = {
  formats: () => apiGet<{ id: string; label: string }[]>("/export/format"),
  trigger: (body: unknown) => apiPost<{ task_id: string }>("/export", body),
  taskStatus: (taskId: string) => apiGet<ExportTaskResult>(`/export/task/${taskId}`),
};
