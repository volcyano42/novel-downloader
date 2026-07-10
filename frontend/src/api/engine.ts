import { apiGet, apiPost, apiPut, apiDelete } from "./client";
export const engineApi = {
  list: () => apiGet<{ id: string; mode: string; platform: string }[]>("/engine"),
  create: (body: unknown) => apiPost<{ engine_id: string; mode: string; platform: string }>("/engine/create", body),
  get: (id: string) => apiGet<{ id: string; mode: string; platform: string }>(`/engine/${id}`),
  update: (id: string, body: unknown) => apiPut<{ id: string; mode: string; platform: string }>(`/engine/${id}`, body),
  delete: (id: string) => apiDelete(`/engine/${id}`),
  types: () => apiGet<{ types: string[] }>("/engine/type/list"),
};
