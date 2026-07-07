const BASE_URL = "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message); this.name = "ApiError"; this.status = status;
  }
}

export async function apiFetch<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...options.headers as Record<string, string> ?? {} };
  // 只在有 body 时加 Content-Type，避免 GET 触发不必要的 CORS 预检
  if (options.body) headers["Content-Type"] = "application/json";
  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (!res.ok) { const body = await res.text(); throw new ApiError(res.status, body || res.statusText); }
  return res.json() as Promise<T>;
}

export function apiGet<T = unknown>(path: string) { return apiFetch<T>(path); }
export function apiPost<T = unknown>(path: string, body: unknown) { return apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) }); }
export function apiPut<T = unknown>(path: string, body: unknown) { return apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) }); }
export function apiDelete<T = unknown>(path: string) { return apiFetch<T>(path, { method: "DELETE" }); }
