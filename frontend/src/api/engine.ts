import { apiGet, apiPost, apiDelete } from "./client";
export const engineApi = {
  list: () => apiGet<{ id: string; mode: string }[]>("/engine"),
  create: (body: unknown) => apiPost<{ engine_id: string; mode: string }>("/engine/create", body),
  get: (id: string) => apiGet(`/engine/${id}`),
  delete: (id: string) => apiDelete(`/engine/${id}`),
  types: () => apiGet<{ types: string[] }>("/engine/type/list"),
};
