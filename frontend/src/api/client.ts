const BASE_URL = "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message); this.name = "ApiError"; this.status = status;
  }
}

export async function apiFetch<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { headers: { "Content-Type": "application/json", ...options.headers }, ...options });
  if (!res.ok) { const body = await res.text(); throw new ApiError(res.status, body || res.statusText); }
  return res.json() as Promise<T>;
}

export function apiGet<T = unknown>(path: string) { return apiFetch<T>(path); }
export function apiPost<T = unknown>(path: string, body: unknown) { return apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) }); }
export function apiPut<T = unknown>(path: string, body: unknown) { return apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) }); }
export function apiDelete<T = unknown>(path: string) { return apiFetch<T>(path, { method: "DELETE" }); }
