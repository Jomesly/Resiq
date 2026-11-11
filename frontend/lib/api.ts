import { getToken } from "./workspace";

/** Demo mode is explicit. Normal development talks to the local FastAPI service. */
export const API_BASE = process.env.NEXT_PUBLIC_DEMO_MODE === "true" ? "" : (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = "ApiError";
  }
}

async function send(path: string, init: RequestInit, base: string, token: string): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${token}`);
  if (!base) {
    const { mockFetch } = await import("./mock/server");
    return mockFetch(path, { ...init, headers });
  }
  return fetch(`${base}${path}`, { ...init, headers });
}

async function toError(res: Response): Promise<ApiError> {
  let detail = res.statusText || `Request failed (${res.status})`;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    /* body was not JSON */
  }
  return new ApiError(res.status, detail);
}

export async function apiRaw(path: string, init: RequestInit = {}, base: string = API_BASE): Promise<Response> {
  const tokenFor = () => (base ? getToken(base) : Promise.resolve("mock"));
  const res = await send(path, init, base, await tokenFor());
  if (res.status === 401 && base) {
    throw new ApiError(401, "This browser's workspace could not be opened. Your saved token has been kept. Check that you are connected to the correct server, then retry.");
  }
  if (!res.ok) throw await toError(res);
  return res;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}, base: string = API_BASE): Promise<T> {
  const res = await apiRaw(path, init, base);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
