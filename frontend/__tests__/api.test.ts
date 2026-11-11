import { afterEach, describe, expect, it, vi } from "vitest";
import { getToken, clearToken } from "@/lib/workspace";
import { apiFetch, ApiError } from "@/lib/api";

const BASE = "https://api.test";

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken(BASE);
});

describe("workspace token", () => {
  it("creates a workspace once and reuses the stored token", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(201, { token: "tok-1" }));
    vi.stubGlobal("fetch", fetchMock);
    const [a, b] = await Promise.all([getToken(BASE), getToken(BASE)]);
    expect(a).toBe("tok-1");
    expect(b).toBe("tok-1");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem("resiq.token:" + BASE)).toBe("tok-1");
    await getToken(BASE);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("apiFetch", () => {
  it("sends the bearer token", async () => {
    localStorage.setItem("resiq.token:" + BASE, "tok-9");
    const fetchMock = vi.fn(async () => jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/api/receipts", {}, BASE);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`${BASE}/api/receipts`);
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer tok-9");
  });

  it("on 401 preserves the token and does not silently replace the workspace", async () => {
    localStorage.setItem("resiq.token:" + BASE, "stale");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: "bad token" }))
      .mockResolvedValueOnce(jsonResponse(201, { token: "fresh" }))
      .mockResolvedValueOnce(jsonResponse(200, { items: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiFetch("/api/receipts", {}, BASE)).rejects.toMatchObject({ status: 401 });
    expect(localStorage.getItem("resiq.token:" + BASE)).toBe("stale");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("throws ApiError with status and detail", async () => {
    localStorage.setItem("resiq.token:" + BASE, "t");
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(409, { detail: "Still reading" })));
    await expect(apiFetch("/api/receipts/x", { method: "PUT" }, BASE)).rejects.toMatchObject({
      status: 409,
      detail: "Still reading",
    });
    await expect(apiFetch("/api/receipts/x", {}, BASE)).rejects.toBeInstanceOf(ApiError);
  });
});

