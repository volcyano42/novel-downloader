/** API v2 客户端 — /api/v2，响应结构 { ok, message, data } */

const BASE_URL = "/api/v2";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface ApiResponse<T = unknown> {
  ok: boolean;
  message: string;
  data: T;
}

async function parseError(res: Response): Promise<never> {
  try {
    const body = await res.json() as ApiResponse;
    throw new ApiError(res.status, body.message || res.statusText);
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(res.status, res.statusText);
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
  baseUrl = BASE_URL,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> ?? {}),
  };
  if (options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }
  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, "网络连接失败");
  }
  if (!res.ok) await parseError(res);
  const body = await res.json();
  return (body as ApiResponse<T>).data;
}

export function apiGet<T = unknown>(path: string, signal?: AbortSignal, baseUrl?: string) {
  return apiFetch<T>(path, { signal }, baseUrl);
}

export function apiPost<T = unknown>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
  baseUrl?: string,
) {
  return apiFetch<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  }, baseUrl);
}

export function apiPut<T = unknown>(path: string, body: unknown, baseUrl?: string) {
  return apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) }, baseUrl);
}

export function apiDelete<T = unknown>(path: string) {
  return apiFetch<T>(path, { method: "DELETE" });
}
