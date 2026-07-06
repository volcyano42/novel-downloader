import { apiGet, apiPost } from "./client";
export const exportApi = {
  formats: () => apiGet<{ id: string; label: string }[]>("/export/format"),
  trigger: (body: unknown) => apiPost<{ task_id: string }>("/export", body),
  taskStatus: (taskId: string) => apiGet<{ task_id: string; status: string; progress: number }>(`/export/task/${taskId}`),
};
