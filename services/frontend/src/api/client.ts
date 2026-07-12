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
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> ?? {}),
  };
  if (options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, "网络连接失败");
  }
  if (!res.ok) await parseError(res);
  const body = (await res.json()) as ApiResponse<T>;
  return body.data;
}

export function apiGet<T = unknown>(path: string, signal?: AbortSignal) {
  return apiFetch<T>(path, { signal });
}

export function apiPost<T = unknown>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
) {
  return apiFetch<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}

export function apiPut<T = unknown>(path: string, body: unknown) {
  return apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

export function apiDelete<T = unknown>(path: string) {
  return apiFetch<T>(path, { method: "DELETE" });
}
